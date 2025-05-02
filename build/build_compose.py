import yaml
import csv
from collections import defaultdict
import os


class Grafo:
    def __init__(self, caminho_csv):
        self.conexoes = []
        self.roteadores = set()
        self.carregar_conexoes(caminho_csv)

    def carregar_conexoes(self, caminho_csv):
        """Carrega as conexões a partir de um arquivo CSV."""
        # Certifica-se de que o caminho está correto
        caminho_csv = os.path.abspath(caminho_csv)  # Obtém o caminho absoluto para evitar problemas de diretório
        with open(caminho_csv, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                origem, destino, peso = row['no_origem'], row['no_destino'], int(row['peso'])
                self.conexoes.append((origem, destino, peso))
                self.roteadores.update([origem, destino])

    def get_conexoes(self):
        return self.conexoes

    def get_roteadores(self):
        return self.roteadores


class RedeDockerCompose:
    def __init__(self, grafo: Grafo):
        self.grafo = grafo
        self.conexoes_por_roteador = defaultdict(list)
        self.subnet_base = "10.10.{0}.0/24"
        self.ip_base = "10.10.{0}.{1}"
        self.networks = {}
        self.ip_map = defaultdict(dict)
        self.subnet_count = 1
        self.subnet_cost = {}
        self.docker_compose = {
            'version': '3.9',  # A versão sempre deve ser no topo
            'services': {}  # Aqui vamos colocar os serviços primeiro
        }

    def montar_conexoes_por_roteador(self):
        """Organiza as conexões por roteador."""
        for origem, destino, peso in self.grafo.get_conexoes():
            self.conexoes_por_roteador[origem].append(destino)
            self.conexoes_por_roteador[destino].append(origem)

    def definir_redes_e_ips(self):
        """Define as redes e os IPs para as conexões."""
        for origem, destino, peso in self.grafo.get_conexoes():
            net_name = f"{origem}_{destino}_net"
            subnet = self.subnet_base.format(self.subnet_count)
            self.ip_map[origem][net_name] = self.ip_base.format(self.subnet_count, 2)
            self.ip_map[destino][net_name] = self.ip_base.format(self.subnet_count, 3)
            self.networks[net_name] = subnet
            self.subnet_cost[net_name] = peso
            self.subnet_count += 1

    def definir_servicos_roteadores(self):
        """Define os serviços para cada roteador no Docker Compose."""
        for roteador in sorted(self.grafo.get_roteadores()):
            service = {
                'build': './router',
                'container_name': roteador,
                'environment': {
                    'CONTAINER_NAME': roteador,
                },
                'volumes': [
                    './router/router.py:/app/router.py'
                ],
                'networks': {}
            }
            for net, ip in self.ip_map[roteador].items():
                service['networks'][net] = {'ipv4_address': ip}
                service['environment'][f"CUSTO_{net}"] = str(self.subnet_cost[net])
            service['cap_add'] = ['NET_ADMIN']

            self.docker_compose['services'][roteador] = service

    def definir_hosts(self):
        """Cria uma rede exclusiva entre cada roteador e seus hosts, conectando dois hosts a um único roteador."""
        for roteador in sorted(self.grafo.get_roteadores()):
            net_name = f"{roteador}_hosts_net"
            subnet = self.subnet_base.format(self.subnet_count)
            self.networks[net_name] = subnet
            self.subnet_count += 1

            # IPs para roteador e dois hosts
            roteador_ip = self.ip_base.format(self.subnet_count - 1, 1)
            host1_ip = self.ip_base.format(self.subnet_count - 1, 2)
            host2_ip = self.ip_base.format(self.subnet_count - 1, 3)

            # Adiciona a rede no roteador
            self.ip_map[roteador][net_name] = roteador_ip
            self.subnet_cost[net_name] = 1  # Custo fictício para rede local

            for i, host_ip in enumerate([host1_ip, host2_ip], start=1):
                host_name = f"{roteador}_h{i}"
                self.docker_compose['services'][host_name] = {
                    'build': './host',
                    'container_name': host_name,
                    'networks': {
                        net_name: {'ipv4_address': host_ip}
                    },
                }

    def definir_networks(self):
        """Define as redes dentro do Docker Compose.""" 
        self.docker_compose['networks'] = {}
        for net, subnet in self.networks.items():
            self.docker_compose['networks'][net] = {
                'driver': 'bridge',
                'ipam': {
                    'config': [{'subnet': subnet}]
                }
            }

    def gerar_docker_compose(self, caminho_saida="docker-compose.yml"):
        """Gera e salva o arquivo docker-compose.yml."""
        self.montar_conexoes_por_roteador()
        self.definir_redes_e_ips()
        self.definir_hosts()  # <- Mova esta linha para antes de definir os serviços dos roteadores
        self.definir_servicos_roteadores()  # Agora os roteadores terão os IPs das redes de host
        self.definir_networks()

        with open(caminho_saida, "w") as f:
            yaml.dump(self.docker_compose, f, default_flow_style=False, sort_keys=False)

        print(f"Docker Compose salvo em: {caminho_saida}")



class GeradorDockerCompose:
    def __init__(self, caminho_csv):
        self.grafo = Grafo(caminho_csv)
        self.rede = RedeDockerCompose(self.grafo)

    def gerar(self, caminho_saida="docker-compose.yml"):
        self.rede.gerar_docker_compose(caminho_saida)


if __name__ == '__main__':
    # Ajuste o caminho para o arquivo CSV
    caminho_csv = "graph\\grafo.csv"
    caminho_saida = "docker-compose.yml"

    gerador = GeradorDockerCompose(caminho_csv)
    gerador.gerar(caminho_saida)
