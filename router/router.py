import time
import psutil
import socket
import threading
import json
import os
import subprocess
import ipaddress


#--------------------------------------LSDB--------------------------------------------------------------------------#

class TabelaLSA:

    def __init__(self):
        self._tabela = {}

    def criar_entrada(self, sequence_number, timestamp, addresses, links):
        return {
            "sequence_number": sequence_number,
            "timestamp": timestamp,
            "addresses": addresses,
            "links": links,
        }

    def get(self, router_id):
        return self._tabela.get(router_id)

    def atualizar_entrada(self, pacote):
        router_id = pacote["router_id"]
        sequence_number = pacote["sequence_number"]
        entrada = self.get(router_id)

        if entrada and sequence_number <= entrada["sequence_number"]:
            return False

        self._tabela[router_id] = self.criar_entrada(
            sequence_number, pacote["timestamp"], pacote["addresses"], pacote["links"])

        for vizinho in pacote["links"].keys():
            if vizinho not in self._tabela:
                print(f"[LSDB] Descoberto novo roteador: {vizinho}")
                self._tabela[vizinho] = self.criar_entrada(-1, 0, [], {})

        return True

    def keys(self):
        return self._tabela.keys()

    def links(self, router_id):
        return self._tabela[router_id]["links"]

    def addresses(self, router_id):
        return self._tabela[router_id]["addresses"]


class CalculadoraCaminhos:

    def __init__(self, router_id, tabela_lsa: TabelaLSA):
        self.router_id = router_id
        self.tabela = tabela_lsa

    def dijkstra(self):
        distancias = {r: float('inf') for r in self.tabela.keys()}
        caminhos = {r: None for r in self.tabela.keys()}
        marcados = {}

        distancias[self.router_id] = 0

        while len(marcados) < len(distancias):
            roteador = min((n for n in distancias if n not in marcados),
                           key=lambda x: distancias[x], default=None)

            if roteador is None:
                break

            marcados[roteador] = True
            for vizinho, custo in self.tabela.links(roteador).items():
                if vizinho not in marcados:
                    novo_custo = distancias[roteador] + custo
                    if novo_custo < distancias[vizinho]:
                        distancias[vizinho] = novo_custo
                        caminhos[vizinho] = roteador

        return caminhos


class GerenciadorRotas:

    def __init__(self, router_id, tabela_lsa: TabelaLSA, neighbors_ip: dict[str, str]):
        self.router_id = router_id
        self.tabela = tabela_lsa
        self.neighbors_ip = neighbors_ip
        self._roteamento = {}

    def atualizar_proximo_pulo(self, caminhos: dict):
        for destino in caminhos:
            if destino != self.router_id:
                pulo = destino
                while pulo is not None and caminhos[pulo] != self.router_id:
                    pulo = caminhos[pulo]
                self._roteamento[destino] = pulo
        self._roteamento = dict(sorted(self._roteamento.items()))

    def atualizar_rotas(self):
        for destino, gateway in self._roteamento.items():
            if gateway not in self.neighbors_ip:
                print(f"[LSDB] Ignorando rota para {destino} via {gateway}: gateway não conhecido ainda")
                continue

            for ip_destino in self.tabela.addresses(destino):
                ip_gateway = self.neighbors_ip[gateway]
                comando = ["ip", "route", "replace", ip_destino, "via", ip_gateway]

                try:
                    subprocess.run(comando, check=True)
                    print(f"Rota adicionada: {ip_destino} -> {ip_gateway}")
                except subprocess.CalledProcessError as e:
                    print(f"[ERRO] Falha ao adicionar rota: [{comando}] -> [{e}]")


class LSDB:

    def __init__(self, router_id: str, neighbors_ip: dict[str, str]):
        self._router_id = router_id
        self._tabela = TabelaLSA()
        self._caminhos = CalculadoraCaminhos(router_id, self._tabela)
        self._gerenciador_rotas = GerenciadorRotas(router_id, self._tabela, neighbors_ip)

    def atualizar(self, pacote):
        if not self._tabela.atualizar_entrada(pacote):
            return False

        caminhos = self._caminhos.dijkstra()
        self._gerenciador_rotas.atualizar_proximo_pulo(caminhos)
        self._gerenciador_rotas.atualizar_rotas()
        return True
    
    #-------------------------------HELLO SENDER---------------------------------------------------#
    #enviaO periodico de pacotes do tipo "HELLO" via broadcast para interfaces de rede específicas#



class HelloPacketBuilder:
    def __init__(self, router_id: str, neighbors: dict[str, str]):
        self._router_id = router_id
        self._neighbors = neighbors

    def criar_pacote(self, ip_address: str):
        return {
            "type": "HELLO",
            "router_id": self._router_id,
            "timestamp": time.time(),
            "ip_address": ip_address,
            "known_neighbors": list(self._neighbors.keys()),
        }


class HelloBroadcaster:
    def __init__(self, router_id: str, port: int, interval: int, packet_builder: HelloPacketBuilder):
        self._router_id = router_id
        self._PORTA = port
        self._interval = interval
        self._packet_builder = packet_builder

    def enviar_broadcast(self, ip_address: str, broadcast_ip: str):
        sock = create_socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while True:
            pacote = self._packet_builder.criar_pacote(ip_address)
            message = json.dumps(pacote).encode("utf-8")

            try:
                sock.sendto(message, (broadcast_ip, self._PORTA))
                print(f"[{self._router_id}] Pacote HELLO enviado para {broadcast_ip}")
            except Exception as e:
                print(f"[{self._router_id}] Erro ao enviar: {e}")

            time.sleep(self._interval)


class HelloSender:
    def __init__(self, router_id: str, interfaces: list[dict[str, str]], neighbors: dict[str, str], interval: int = 10, port: int = 5000):
        self._interfaces = interfaces
        self._packet_builder = HelloPacketBuilder(router_id, neighbors)
        self._broadcaster = HelloBroadcaster(router_id, port, interval, self._packet_builder)

    def iniciar(self):
        interfaces = [item for item in self._interfaces if "broadcast" in item]
        print(interfaces)

        for interface_info in interfaces:
            ip_address = interface_info["address"]
            broadcast_ip = interface_info["broadcast"]

            if broadcast_ip is not None:
                thread_emissor = threading.Thread(
                    target=self._broadcaster.enviar_broadcast,
                    args=(ip_address, broadcast_ip),
                    daemon=True
                )
                thread_emissor.start()

#---------------------------------------------LSASender---------------------------------------------------------------#


class LSAPacketBuilder:
    def __init__(self, router_id: str, neighbors_cost: dict[str, int], interfaces: list[dict[str, str]]):
        self._router_id = router_id
        self._neighbors_cost = neighbors_cost
        self._interfaces = interfaces
        self._sequence_number = 0

    def criar_pacote(self):
        self._sequence_number += 1
        return {
            "type": "LSA",
            "router_id": self._router_id,
            "timestamp": time.time(),
            "addresses": [item["address"] for item in self._interfaces],
            "sequence_number": self._sequence_number,
            "links": dict(self._neighbors_cost)
        }


class LSABroadcaster:
    def __init__(self, router_id: str, neighbors_ip: dict[str, str], port: int, interval: int, lsdb):
        self._router_id = router_id
        self._neighbors_ip = neighbors_ip
        self._PORTA = port
        self._interval = interval
        self._lsdb = lsdb

    def enviar_periodicamente(self, packet_builder: LSAPacketBuilder):
        sock = create_socket()
        while True:
            pacote = packet_builder.criar_pacote()
            self._lsdb.atualizar(pacote)
            message = json.dumps(pacote).encode("utf-8")

            for ip in self._neighbors_ip.values():
                try:
                    sock.sendto(message, (ip, self._PORTA))
                    print(f"[{self._router_id}] Pacote LSA enviado para {ip}")
                except Exception as e:
                    print(f"[{self._router_id}] Erro ao enviar: {e}")

            time.sleep(self._interval)

    def encaminhar_para_vizinhos(self, pacote: dict, neighbor_ip: str):
        sock = create_socket()
        message = json.dumps(pacote).encode("utf-8")

        for ip in self._neighbors_ip.values():
            if ip != neighbor_ip:
                try:
                    sock.sendto(message, (ip, self._PORTA))
                    print(f"[{self._router_id}] Pacote LSA encaminhado para {ip}")
                except Exception as e:
                    print(f"[{self._router_id}] Erro ao encaminhar: {e}")


class LSASender:
    def __init__(self, router_id: str, neighbors_ip: dict[str, str], neighbors_cost: dict[str, int],
                 interfaces: list[dict[str, str]], lsdb, interval: int = 30, port: int = 5000):
        self._router_id = router_id
        self._iniciado = False
        self._packet_builder = LSAPacketBuilder(router_id, neighbors_cost, interfaces)
        self._broadcaster = LSABroadcaster(router_id, neighbors_ip, port, interval, lsdb)

    def iniciar(self):
        if not self._iniciado:
            self._iniciado = True
            thread_emissor = threading.Thread(
                target=self._broadcaster.enviar_periodicamente,
                args=(self._packet_builder,),
                daemon=True
            )
            thread_emissor.start()

    def encaminhar(self, pacote: dict, neighbor_ip: str):
        self._broadcaster.encaminhar_para_vizinhos(pacote, neighbor_ip)


#--------------------------ROTEADOR----------------------------#

import socket
import threading
import time
import json
import psutil
import ipaddress


class InterfaceManager:
    @staticmethod
    def listar_enderecos():
        interfaces = psutil.net_if_addrs()
        interfaces_list = []
        for interface, addresses in interfaces.items():
            if interface.startswith("eth"):
                for address in addresses:
                    if address.family == socket.AF_INET:
                        if address.address.startswith("192"):
                            ip = ipaddress.ip_address(address.address)
                            rede = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                            interfaces_list.append({"address": f"{rede.network_address}/24"})
                        else:
                            interfaces_list.append({
                                "address": address.address,
                                "broadcast": address.broadcast
                            })
        return interfaces_list


class ReceptorPacotes:
    def __init__(self, router_id, porta, buffer_size, gerenciador_vizinhos):
        self._router_id = router_id
        self._PORTA = porta
        self._BUFFER_SIZE = buffer_size
        self._gerenciador_vizinhos = gerenciador_vizinhos

    def iniciar(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self._PORTA))

        while True:
            try:
                data, address = sock.recvfrom(self._BUFFER_SIZE)
                mensagem = data.decode("utf-8")
                pacote = json.loads(mensagem)
                tipo_pacote = pacote.get("type")
                received_id = pacote.get("router_id")
                if received_id != self._router_id:
                    received_ip = address[0]
                    print(f"Pacote {tipo_pacote} recebido de [{received_id}] {received_ip}")

                    if tipo_pacote == "HELLO":
                        self._gerenciador_vizinhos.processar_hello(pacote, received_ip)
                    elif tipo_pacote == "LSA":
                        self._gerenciador_vizinhos.processar_lsa(pacote, received_ip)

            except Exception as e:
                print(f"Erro ao receber pacote: {e}")


class InicializadorRoteador:
    def __init__(self, receptor, hello_sender):
        self._receptor = receptor
        self._hello_sender = hello_sender

    def iniciar(self):
        thread_receptor = threading.Thread(target=self._receptor.iniciar, daemon=True)
        thread_receptor.start()
        self._hello_sender.iniciar()

        while True:
            time.sleep(1)


class Roteador:
    __slots__ = ["_router_id", "_interfaces", "_PORTA", "_lsa", "_lsdb", "_BUFFER_SIZE",
                 "_neighbors_detected", "_neighbors_recognized", "_gerenciador_vizinhos"]

    def __init__(self, router_id: str, PORTA: int = 5000, BUFFER_SIZE: int = 4096):
        self._router_id = router_id
        self._interfaces = InterfaceManager.listar_enderecos()
        self._PORTA = PORTA
        self._BUFFER_SIZE = BUFFER_SIZE
        self._neighbors_detected = {}
        self._neighbors_recognized = {}

        self._lsdb = LSDB(router_id, self._neighbors_recognized)
        self._lsa = LSASender(router_id, self._neighbors_recognized,
                              self._neighbors_detected, self._interfaces, self._lsdb)
        self._gerenciador_vizinhos = GerenciadorVizinhos(router_id, self._lsa, self._lsdb)

    def iniciar(self):
        hello = HelloSender(self._router_id, self._interfaces, self._neighbors_detected)
        receptor = ReceptorPacotes(self._router_id, self._PORTA,
                                   self._BUFFER_SIZE, self._gerenciador_vizinhos)
        inicializador = InicializadorRoteador(receptor, hello)
        inicializador.iniciar()

#-------------------------gerenciador de vizinhos---------------------------------------------#

class CalculadoraCusto:
    @staticmethod
    def obter(router_id: str, neighbor_id: str) -> int:
        custo = os.getenv(f"CUSTO_{router_id}_{neighbor_id}_net")
        if custo is None:
            custo = os.getenv(f"CUSTO_{neighbor_id}_{router_id}_net")
        if custo is None:
            raise ValueError(f"Custo não definido para {router_id} <-> {neighbor_id}")
        return int(custo)


class ProcessadorHello:
    def __init__(self, router_id: str, neighbors_detected: dict, neighbors_recognized: dict, lsa):
        self._router_id = router_id
        self._neighbors_detected = neighbors_detected
        self._neighbors_recognized = neighbors_recognized
        self._lsa = lsa

    def processar(self, pacote: dict, received_ip: str, custo: int):
        received_id = pacote.get("router_id")
        self._neighbors_detected[received_id] = custo
        neighbors = pacote.get("known_neighbors")

        if neighbors and self._router_id in neighbors and received_id not in self._neighbors_recognized:
            self._neighbors_recognized[received_id] = received_ip
            self._lsa.iniciar()



class ProcessadorLSA:
    def __init__(self, lsdb, lsa):
        self._lsdb = lsdb
        self._lsa = lsa

    def processar(self, pacote: dict, received_ip: str):
        if self._lsdb.atualizar(pacote):
            self._lsa.encaminhar_para_vizinhos(pacote, received_ip)


class GerenciadorVizinhos:

    __slots__ = ["_router_id", "_lsa", "_lsdb",
                 "_neighbors_detected", "_neighbors_recognized",
                 "_hello_processor", "_lsa_processor"]

    def __init__(self, router_id: str, lsa, lsdb):
        self._router_id = router_id
        self._lsa = lsa
        self._lsdb = lsdb
        self._neighbors_detected = lsa.neighbors_cost
        self._neighbors_recognized = lsa.neighbors_ip

        self._hello_processor = ProcessadorHello(router_id, self._neighbors_detected, self._neighbors_recognized, lsa)
        self._lsa_processor = ProcessadorLSA(lsdb, lsa)

    def processar_hello(self, pacote: dict, received_ip: str):
        received_id = pacote.get("router_id")
        if received_id is None:
            return  # ou você pode lançar um erro, se isso for inesperado

        custo = CalculadoraCusto.obter(self._router_id, received_id)
        self._hello_processor.processar(pacote, received_ip, custo)


    def processar_lsa(self, pacote: dict, received_ip: str):
        self._lsa_processor.processar(pacote, received_ip)

    def get_custo(self, router_id: str, neighbor_id: str):
        return CalculadoraCusto.obter(router_id, neighbor_id)

#----------------------------------------------------------------------------------------------------------------------#

def create_socket():
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)




if (__name__ == "__main__"):
    router_id = os.getenv("CONTAINER_NAME")
    if (not router_id):
        raise ValueError(
            "CONTAINER_NAME não definido nas variáveis de ambiente")

    roteador = Roteador(router_id)
    roteador.iniciar()