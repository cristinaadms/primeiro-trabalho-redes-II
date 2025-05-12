"""
Este módulo realiza a leitura de um grafo a partir de um arquivo CSV contendo conexões entre nós
e gera um arquivo Docker Compose para simular uma rede de roteadores e hosts conectados.

Classes:
    - LeitorGrafoCSV: Lê conexões de um grafo a partir de um CSV.
    - ConexaoRede: Representa uma conexão entre dois roteadores.
    - ConfiguracaoRoteador: Define a configuração de um roteador no Docker Compose.
    - ConfiguracaoHost: Define a configuração de um host no Docker Compose.
    - DockerCompose: Constrói a estrutura de redes e serviços no Docker Compose.

Função:
    - dockercompose_build(caminho_csv, caminho_saida): Executa a leitura do CSV e gera o arquivo docker-compose.yml.
"""

import yaml
import csv
from collections import defaultdict


class LeitorGrafoCSV:
    """
        Classe responsável por ler o arquivo CSV com conexões entre roteadores.

        Atributos:
            caminho_arquivo (str): Caminho do arquivo CSV.
            lista_conexoes (list): Lista de tuplas contendo conexões (origem, destino, peso).
            conjunto_roteadores (set): Conjunto de todos os roteadores encontrados.

        Métodos:
            carregar_conexoes(): Lê o CSV e retorna uma lista de conexões e uma lista de roteadores únicos.
    """

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
    """
        Classe que representa uma conexão entre dois roteadores em uma subrede.

        Atributos:
            identificador (str): Nome da subrede.
            subrede (str): Endereço da subrede.
            endereco_origem (str): IP do roteador de origem.
            endereco_destino (str): IP do roteador de destino.
            custo_conexao (int): Custo associado à conexão.
    """

    def __init__(self, identificador, subrede, endereco_origem, endereco_destino, custo_conexao):
        self.identificador = identificador
        self.subrede = subrede
        self.endereco_origem = endereco_origem
        self.endereco_destino = endereco_destino
        self.custo_conexao = custo_conexao

class ConfiguracaoRoteador:
    """
        Classe que define a configuração de um roteador no Docker Compose.

        Atributos:
            nome_roteador (str): Nome do roteador.
            configuracao (dict): Dicionário contendo a configuração do serviço no Compose.

        Métodos:
            adicionar_rede_com_custo(nome_rede, endereco_ip, custo_rede): Adiciona rede de roteador com custo.
            adicionar_rede_hosts(nome_rede, endereco_gateway): Adiciona rede para hosts conectados ao roteador.
            obter_configuracao(): Retorna a configuração do roteador.
    """

    def __init__(self, nome_roteador):
        self.nome_roteador = nome_roteador
        self.configuracao = {
            'build': './router',
            'container_name': nome_roteador,
            'environment': {
                'CONTAINER_NAME': nome_roteador,
            },
            'volumes': [
                './router/router.py:/app/router.py'
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
    """
        Classe que define a configuração de um host no Docker Compose.

        Atributos:
            configuracao (dict): Dicionário contendo a configuração do host.

        Métodos:
            obter_configuracao(): Retorna a configuração do host.
    """

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
    """
        Classe responsável por montar a estrutura completa do arquivo docker-compose.yml.

        Atributos:
            subrede_roteadores (str): Template para subredes de roteadores.
            ip_roteadores (str): Template para IPs de roteadores.
            subrede_hosts (str): Template para subredes de hosts.
            estrutura_compose (dict): Estrutura do arquivo Compose.
            mapa_subredes (dict): Mapeia nome da subrede para seu endereço.
            custos_subredes (dict): Mapeia nome da subrede para o custo da conexão.
            mapa_ips (defaultdict): Mapeia roteadores e subredes para seus IPs.
            contador_subredes (int): Contador usado para criar subredes únicas.

        Métodos:
            criar_redes_roteadores(lista_conexoes): Cria redes e define IPs para roteadores.
            adicionar_roteadores_com_hosts(lista_roteadores): Adiciona serviços de roteadores e hosts.
            construir_redes(): Cria as definições das redes para o Compose.
            salvar_arquivo_compose(caminho_destino): Salva o conteúdo no formato YAML.
    """

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

            for nome_rede, ip_roteador in self.mapa_ips[nome_roteador].items():
                custo_rede = self.custos_subredes[nome_rede]
                roteador.adicionar_rede_com_custo(nome_rede, ip_roteador, custo_rede)

            nome_rede_hosts = f"{nome_roteador}_hosts_net"
            subrede_hosts = self.subrede_hosts.format(self.contador_subredes)
            self.mapa_subredes[nome_rede_hosts] = subrede_hosts

            ip_gateway = f"192.168.{self.contador_subredes}.2"
            roteador.adicionar_rede_hosts(nome_rede_hosts, ip_gateway)

            self.estrutura_compose['services'][nome_roteador] = roteador.obter_configuracao()

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
    """
        Executa o processo completo de geração do docker-compose.yml a partir de um CSV.

        Parâmetros:
            caminho_csv (str): Caminho para o arquivo CSV contendo o grafo.
            caminho_saida (str): Caminho de destino do arquivo docker-compose gerado. Padrão: 'docker-compose.yml'.

        Etapas:
            - Lê o grafo do CSV.
            - Cria redes entre roteadores.
            - Adiciona roteadores com seus respectivos hosts.
            - Cria as redes no Compose.
            - Salva o arquivo YAML no destino.
    """

    leitor = LeitorGrafoCSV(caminho_csv)  
    conexoes, roteadores = leitor.carregar_conexoes()  

    builder = DockerCompose()
    builder.criar_redes_roteadores(conexoes)  
    builder.adicionar_roteadores_com_hosts(roteadores) 
    builder.construir_redes()  
    builder.salvar_arquivo_compose(caminho_saida)  


if __name__ == '__main__':
    dockercompose_build("graph\\grafo.csv")