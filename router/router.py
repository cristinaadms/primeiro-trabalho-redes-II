import time
import psutil
import socket
import threading
import json
import heapq
import os


def criar_socket_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return sock


class GerenciadorInterfaces:
    def obter_interfaces_ativas(self):
        interfaces = psutil.net_if_addrs()
        lista_interfaces = []

        for nome, enderecos in interfaces.items():
            if nome.startswith("eth"):
                for endereco in enderecos:
                    if endereco.family == socket.AF_INET:
                        lista_interfaces.append({
                            "ip": endereco.address,
                            "broadcast": endereco.broadcast
                        })
        return lista_interfaces


class BancoDeTopologia:
    __slots__ = ["_id_local", "_tabela_topologica", "_rotas", "_vizinhos_ip"]

    def __init__(self, id_local: str, vizinhos_ip: dict):
        self._id_local = id_local
        self._tabela_topologica = {}
        self._rotas = {}
        self._vizinhos_ip = vizinhos_ip

    def _criar_entrada(self, sequence_number, timestamp, addresses, links):
        return {
            "sequence_number": sequence_number,
            "timestamp": timestamp,
            "addresses": addresses,
            "links": links
        }

    def atualizar_topologia(self, pacote_lsa):
        remetente = pacote_lsa["router_id"]
        sequence_number = pacote_lsa["sequence_number"]

        entrada_atual = self._tabela_topologica.get(remetente)
        if entrada_atual and entrada_atual["sequence_number"] >= sequence_number:
            return

        self._tabela_topologica[remetente] = self._criar_entrada(
            sequence_number,
            pacote_lsa["timestamp"],
            pacote_lsa["addresses"],
            pacote_lsa["links"]
        )

        for vizinho in pacote_lsa["links"].keys():
            if vizinho not in self._tabela_topologica:
                print(f"[LSDB] Descoberto novo roteador: {vizinho}")
                self._tabela_topologica[vizinho] = self._criar_entrada(-1, 0, [], {})

        caminhos = self._executar_dijkstra()
        self._atualizar_rotas(caminhos)

    def _executar_dijkstra(self):
        distancias = {no: float('inf') for no in self._tabela_topologica}
        caminhos = {no: None for no in self._tabela_topologica}
        marcados = {}

        distancias[self._id_local] = 0

        while len(marcados) < len(self._tabela_topologica):
            atual = None
            menor = float('inf')
            for no, custo in distancias.items():
                if no not in marcados and custo < menor:
                    atual = no
                    menor = custo

            if atual is None:
                break

            marcados[atual] = True
            vizinhos = self._tabela_topologica[atual]["links"]
            for vizinho, custo in vizinhos.items():
                if vizinho not in marcados:
                    nova_dist = distancias[atual] + custo
                    if nova_dist < distancias[vizinho]:
                        distancias[vizinho] = nova_dist
                        caminhos[vizinho] = atual

        return caminhos

    def _atualizar_rotas(self, caminhos):
        self._rotas = {}
        for destino in caminhos:
            if destino == self._id_local or caminhos[destino] is None:
                continue
            anterior = destino
            while caminhos[anterior] != self._id_local:
                anterior = caminhos[anterior]
            self._rotas[destino] = anterior

        print(f"[LSDB] Rotas atualizadas: {json.dumps(self._rotas, indent=4)}")


class GerenciadorHello:
    __slots__ = ["_id_roteador", "_interfaces", "_vizinhos", "_intervalo", "_porta"]

    def __init__(self, id_roteador: str, interfaces: list, vizinhos: dict, intervalo=10, porta=5000):
        self._id_roteador = id_roteador
        self._interfaces = interfaces
        self._vizinhos = vizinhos
        self._intervalo = intervalo
        self._porta = porta

    def _montar_pacote_hello(self, ip_origem):
        return {
            "tipo": "HELLO",
            "id_roteador": self._id_roteador,
            "timestamp": time.time(),
            "ip_origem": ip_origem,
            "vizinhos_conhecidos": list(self._vizinhos.keys())
        }

    def _executar_envio_periodico(self, ip_local, ip_broadcast):
        sock = criar_socket_udp()
        while True:
            pacote = self._montar_pacote_hello(ip_local)
            try:
                sock.sendto(json.dumps(pacote).encode(), (ip_broadcast, self._porta))
                print(f"[{self._id_roteador}] HELLO enviado via {ip_local} -> {ip_broadcast}")
            except Exception as erro:
                print(f"[{self._id_roteador}] Falha ao enviar HELLO: {erro}")
            time.sleep(self._intervalo)

    def iniciar_envio(self):
        for interface in self._interfaces:
            if interface["broadcast"]:
                threading.Thread(
                    target=self._executar_envio_periodico,
                    args=(interface["ip"], interface["broadcast"]),
                    daemon=True
                ).start()


class DispositivoDeRoteamento:
    __slots__ = ["_id", "_interfaces", "_porta", "_buffer", "_vizinhos", "_lsdb"]

    def __init__(self, id_roteador, interfaces, porta=5000, buffer=4096):
        self._id = id_roteador
        self._interfaces = interfaces
        self._porta = porta
        self._buffer = buffer
        self._vizinhos = {}
        self._lsdb = BancoDeTopologia(id_roteador, self._vizinhos)

    def _escutar_pacotes(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('', self._porta))
            print(f"[{self._id}] Escutando HELLOs na porta {self._porta}...")

            while True:
                try:
                    dados, endereco = sock.recvfrom(self._buffer)
                    pacote = json.loads(dados.decode())
                    if pacote.get("tipo") == "HELLO" and pacote["id_roteador"] != self._id:
                        print(f"[{self._id}] Recebido HELLO de {pacote['id_roteador']} via {endereco[0]}")
                        self._vizinhos[pacote["id_roteador"]] = endereco[0]
                        self._atualizar_lsdb_com_vizinho(pacote)
                except Exception as erro:
                    print(f"[{self._id}] Erro ao receber pacote: {erro}")

    def _atualizar_lsdb_com_vizinho(self, pacote_hello):
        links = {v: 1 for v in pacote_hello["vizinhos_conhecidos"]}  # custo fixo 1
        pacote_lsa = {
            "tipo": "LSA",
            "router_id": pacote_hello["id_roteador"],
            "timestamp": time.time(),
            "sequence_number": int(time.time()),
            "addresses": [pacote_hello["ip_origem"]],
            "links": links
        }
        self._lsdb.atualizar_topologia(pacote_lsa)

    def iniciar_operacao(self):
        threading.Thread(target=self._escutar_pacotes, daemon=True).start()
        GerenciadorHello(self._id, self._interfaces, self._vizinhos, porta=self._porta).iniciar_envio()
        while True:
            time.sleep(1)


def main():
    id_roteador = os.getenv('CONTAINER_NAME') or exit("Erro: CONTAINER_NAME não definido")
    interfaces = GerenciadorInterfaces().obter_interfaces_ativas()
    DispositivoDeRoteamento(id_roteador, interfaces).iniciar_operacao()


if __name__ == "__main__":
    main()
