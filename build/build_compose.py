import yaml
import csv
from collections import defaultdict


class LeitorGrafoCSV:
    def __init__(self, caminho_arquivo):
        self.caminho_arquivo = caminho_arquivo
        self.lista_conexoes = []
        self.conjunto_roteadores = set()

    def carregar_conexoes(self):
        with open(self.caminho_arquivo, newline='') as arquivo_csv:
            leitor = csv.DictReader(arquivo_csv)
            for linha in leitor:
                no_origem = linha['no_origem']
                no_destino = linha['no_destino']
                peso = int(linha['peso'])

                self.lista_conexoes.append((no_origem, no_destino, peso))
                self.conjunto_roteadores.update([no_origem, no_destino])

        return self.lista_conexoes, sorted(self.conjunto_roteadores)


class ConexaoRede:
    def __init__(self, identificador, subrede, endereco_origem, endereco_destino, custo_conexao):
        self.identificador = identificador
        self.subrede = subrede
        self.endereco_origem = endereco_origem
        self.endereco_destino = endereco_destino
        self.custo_conexao = custo_conexao

class ConfiguracaoRoteador:
    def __init__(self, nome_roteador):
        self.nome_roteador = nome_roteador
        self.configuracao = {
            'build': './roteador',
            'container_name': nome_roteador,
            'environment': {
                'CONTAINER_NAME': nome_roteador,
            },
            'volumes': [
                './roteador/roteador.py:/app/roteador.py'
            ],
            'networks': {},
            'cap_add': ['NET_ADMIN']
        }

    def adicionar_rede_com_custo(self, nome_rede, endereco_ip, custo_rede):
        self.configuracao['networks'][nome_rede] = {'ipv4_address': endereco_ip}
        self.configuracao['environment'][f"CUSTO_{nome_rede}"] = str(custo_rede)

    def adicionar_rede_hosts(self, nome_rede, endereco_gateway):
        self.configuracao['networks'][nome_rede] = {'ipv4_address': endereco_gateway}

    def obter_configuracao(self):
        return self.configuracao


class ConfiguracaoHost:
    def __init__(self, nome_host, endereco_ip, nome_rede):
        self.configuracao = {
            'build': './host',
            'container_name': nome_host,
            'networks': {
                nome_rede: {'ipv4_address': endereco_ip}
            },
            'cap_add': ['NET_ADMIN']
        }

    def obter_configuracao(self):
        return self.configuracao


class DockerCompose:
    def __init__(self):
        self.subrede_roteadores = "10.10.{0}.0/24"
        self.ip_roteadores = "10.10.{0}.{1}"
        self.subrede_hosts = "192.168.{0}.0/24"

        self.estrutura_compose = {
            'version': '3.9',
            'services': {},
            'networks': {}
        }

        self.mapa_subredes = {}
        self.custos_subredes = {}
        self.mapa_ips = defaultdict(dict)
        self.contador_subredes = 1

    def criar_redes_roteadores(self, lista_conexoes):
        redes_criadas = []

        for origem, destino, custo in lista_conexoes:
            nome_subrede = f"{origem}_{destino}_net"
            subrede = self.subrede_roteadores.format(self.contador_subredes)
            ip_origem = self.ip_roteadores.format(self.contador_subredes, 2)
            ip_destino = self.ip_roteadores.format(self.contador_subredes, 3)

            self.mapa_ips[origem][nome_subrede] = ip_origem
            self.mapa_ips[destino][nome_subrede] = ip_destino

            self.mapa_subredes[nome_subrede] = subrede
            self.custos_subredes[nome_subrede] = custo

            redes_criadas.append(
                ConexaoRede(nome_subrede, subrede, ip_origem, ip_destino, custo)
            )

            self.contador_subredes += 1

        return redes_criadas

    def adicionar_roteadores_com_hosts(self, lista_roteadores):
        for nome_roteador in lista_roteadores:
            roteador = ConfiguracaoRoteador(nome_roteador)

            # Conecta o roteador às redes entre roteadores
            for nome_rede, ip_roteador in self.mapa_ips[nome_roteador].items():
                custo_rede = self.custos_subredes[nome_rede]
                roteador.adicionar_rede_com_custo(nome_rede, ip_roteador, custo_rede)

            # Cria rede exclusiva para os hosts do roteador
            nome_rede_hosts = f"{nome_roteador}_hosts_net"
            subrede_hosts = self.subrede_hosts.format(self.contador_subredes)
            self.mapa_subredes[nome_rede_hosts] = subrede_hosts

            ip_gateway = f"192.168.{self.contador_subredes}.2"
            roteador.adicionar_rede_hosts(nome_rede_hosts, ip_gateway)

            self.estrutura_compose['services'][nome_roteador] = roteador.obter_configuracao()

            # Cria dois hosts conectados à rede do roteador
            for indice in range(1, 3):
                nome_host = f"{nome_roteador}_h{indice}"
                ip_host = f"192.168.{self.contador_subredes}.{indice + 2}"

                host = ConfiguracaoHost(nome_host, ip_host, nome_rede_hosts)
                self.estrutura_compose['services'][nome_host] = host.obter_configuracao()

            self.contador_subredes += 1

    def construir_redes(self):
        for nome_rede, subnet in self.mapa_subredes.items():
            self.estrutura_compose['networks'][nome_rede] = {
                'driver': 'bridge',
                'ipam': {
                    'config': [{'subnet': subnet}]
                }
            }

    def salvar_arquivo_compose(self, caminho_destino):
        with open(caminho_destino, "w") as arquivo:
            yaml.dump(self.estrutura_compose, arquivo, default_flow_style=False, sort_keys=False)
        print(f"Docker Compose salvo em: {caminho_destino}")



def dockercompose_build(caminho_csv, caminho_saida="docker-compose.yml"):
    leitor = LeitorGrafoCSV(caminho_csv)  
    conexoes, roteadores = leitor.carregar_conexoes()  

    builder = DockerCompose()
    builder.criar_redes_roteadores(conexoes)  
    builder.adicionar_roteadores_com_hosts(roteadores) 
    builder.construir_redes()  
    builder.salvar_arquivo_compose(caminho_saida)  


if __name__ == '__main__':
    dockercompose_build("graph\\grafo.csv")