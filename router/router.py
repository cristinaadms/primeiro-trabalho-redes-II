import time
import psutil
import socket
import threading
import json
import heapq
import os


# Utilitário para criar sockets UDP
def criar_socket_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return sock


# Gerenciador de interfaces de rede
class GerenciadorInterfaces:
    def __init__(self):
        pass

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


# Tabela de estados de roteadores e algoritmo de Dijkstra
class BancoDeTopologia:
    __slots__ = ["_id_local", "_tabela_topologica", "_rotas"]

    def __init__(self, id_local: str):
        self._id_local = id_local
        self._tabela_topologica = {}
        self._rotas = {}

    def atualizar_topologia(self, pacote_lsa):
        remetente = pacote_lsa["id_roteador"]
        sequencia = pacote_lsa["numero_sequencial"]

        entrada_atual = self._tabela_topologica.get(remetente)

        if entrada_atual and entrada_atual["numero_sequencial"] > sequencia:
            return  # pacote antigo

        self._tabela_topologica[remetente] = {
            "numero_sequencial": sequencia,
            "timestamp": pacote_lsa["timestamp"],
            "vizinhos": {v["id_vizinho"]: v["custo"] for v in pacote_lsa["links"]}
        }

        for vizinho_id in self._tabela_topologica[remetente]["vizinhos"]:
            if vizinho_id not in self._tabela_topologica:
                print(f"[LSDB] Novo roteador descoberto: {vizinho_id}")
                self._tabela_topologica[vizinho_id] = {
                    "numero_sequencial": -1,
                    "timestamp": 0,
                    "vizinhos": {}
                }

        self._executar_dijkstra()

    def _executar_dijkstra(self):
        distancia: dict[str, float] = {no: float('inf') for no in self._tabela_topologica}
        anterior: dict[str, str | None] = {no: None for no in self._tabela_topologica}
        visitados: set[str] = set()

        distancia[self._id_local] = 0
        fila_prioridade: list[tuple[float, str]] = [(0, self._id_local)]  # (distância, nó)

        while fila_prioridade:
            dist_atual, atual = heapq.heappop(fila_prioridade)

            if atual in visitados:
                continue
            visitados.add(atual)

            for vizinho, custo in self._tabela_topologica[atual]["vizinhos"].items():
                if vizinho not in visitados:
                    nova_dist = dist_atual + custo
                    if nova_dist < distancia[vizinho]:
                        distancia[vizinho] = nova_dist
                        anterior[vizinho] = atual
                        heapq.heappush(fila_prioridade, (nova_dist, vizinho))

        print(f"[LSDB] Caminhos calculados via Dijkstra: {json.dumps(anterior, indent=4)}")



# Responsável por enviar pacotes HELLO
class GerenciadorHello:
    __slots__ = ["_id_roteador", "_interfaces", "_vizinhos_conhecidos", "_intervalo", "_porta"]

    def __init__(self, id_roteador: str, interfaces: list[dict], vizinhos_conhecidos: dict, intervalo: int = 10, porta: int = 5000):
        self._id_roteador = id_roteador
        self._interfaces = interfaces
        self._vizinhos_conhecidos = vizinhos_conhecidos
        self._intervalo = intervalo
        self._porta = porta

    def _montar_pacote_hello(self, ip_origem: str):
        return {
            "tipo": "HELLO",
            "id_roteador": self._id_roteador,
            "timestamp": time.time(),
            "ip_origem": ip_origem,
            "vizinhos_conhecidos": list(self._vizinhos_conhecidos.keys())
        }

    def _executar_envio_periodico(self, ip_local: str, ip_broadcast: str):
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
                thread = threading.Thread(
                    target=self._executar_envio_periodico,
                    args=(interface["ip"], interface["broadcast"]),
                    daemon=True
                )
                thread.start()


# Classe principal do roteador/dispositivo
class DispositivoDeRoteamento:
    __slots__ = ["_id", "_interfaces", "_porta", "_tamanho_buffer", "_lsdb", "_vizinhos"]

    def __init__(self, id_roteador: str, interfaces: list[dict], porta: int = 5000, tamanho_buffer: int = 4096):
        self._id = id_roteador
        self._interfaces = interfaces
        self._porta = porta
        self._tamanho_buffer = tamanho_buffer
        self._vizinhos = {}
        self._lsdb = BancoDeTopologia(self._id)

    def _escutar_pacotes(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('', self._porta))
            print(f"[{self._id}] Escutando HELLOs na porta {self._porta}...")

            while True:
                try:
                    dados, endereco = sock.recvfrom(self._tamanho_buffer)
                    pacote = json.loads(dados.decode())
                    if pacote.get("tipo") == "HELLO" and pacote.get("id_roteador") != self._id:
                        print(f"\n[{self._id}] Recebido HELLO de {pacote['id_roteador']} via {endereco[0]}")
                        self._vizinhos[pacote["id_roteador"]] = endereco[0]
                        self._atualizar_lsdb_com_vizinho(pacote)
                except Exception as erro:
                    print(f"[{self._id}] Erro ao receber pacote: {erro}")

    def _atualizar_lsdb_com_vizinho(self, pacote_hello):
        vizinhos = [(v, 1) for v in pacote_hello["vizinhos_conhecidos"]]  # custo fixo 1
        pacote_lsa = {
            "tipo": "LSA",
            "id_roteador": pacote_hello["id_roteador"],
            "timestamp": time.time(),
            "numero_sequencial": int(time.time()),
            "links": [{"id_vizinho": v[0], "custo": v[1]} for v in vizinhos]
        }
        self._lsdb.atualizar_topologia(pacote_lsa)

    def iniciar_operacao(self):
        emissor = GerenciadorHello(self._id, self._interfaces, self._vizinhos, intervalo=10, porta=self._porta)
        threading.Thread(target=self._escutar_pacotes, daemon=True).start()
        emissor.iniciar_envio()

        while True:
            time.sleep(1)


def main():
    id_roteador = os.getenv('CONTAINER_NAME') or exit("Erro: CONTAINER_NAME não definido")
    interfaces = GerenciadorInterfaces().obter_interfaces_ativas()
    DispositivoDeRoteamento(id_roteador, interfaces).iniciar_operacao()


if __name__ == "__main__":
    main()
