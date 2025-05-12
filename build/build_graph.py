import networkx as nx
import matplotlib.pyplot as plt
import random
import os
import csv

def gerar_grafo_aleatorio(quantidade_nos: int, probabilidade_conexao: float = 0.3, peso_minimo: int = 1, peso_maximo: int = 10):
    """
    Gera um grafo aleatório com pesos nas arestas.

    Args:
        quantidade_nos (int): Número de nós do grafo.
        probabilidade_conexao (float, optional): Probabilidade de conexão entre os nós. Default é 0.3.
        peso_minimo (int, optional): Peso mínimo das arestas. Default é 1.
        peso_maximo (int, optional): Peso máximo das arestas. Default é 10.

    Returns:
        nx.Graph: Grafo gerado com nós rotulados como 'rt0', 'rt1', etc.
    """
    grafo = nx.erdos_renyi_graph(quantidade_nos, probabilidade_conexao)
    
    for no_origem, no_destino in grafo.edges():
        peso = random.randint(peso_minimo, peso_maximo)
        grafo[no_origem][no_destino]['peso'] = peso

    while not nx.is_connected(grafo):
        no_origem, no_destino = random.sample(range(quantidade_nos), 2)
        if not grafo.has_edge(no_origem, no_destino):
            peso = random.randint(peso_minimo, peso_maximo)
            grafo.add_edge(no_origem, no_destino, peso=peso)

    nomes = [f"rt{i}" for i in range(quantidade_nos)]
    mapeamento = dict(zip(grafo.nodes(), nomes))
    grafo = nx.relabel_nodes(grafo, mapeamento)

    return grafo

def salvar_imagem_grafo(grafo: nx.Graph, caminho_imagem: str = 'grafo.png'):
    """
    Gera uma imagem do grafo com rótulos de nós e pesos nas arestas e a salva como arquivo PNG.

    Args:
        grafo (nx.Graph): Grafo a ser visualizado.
        caminho_imagem (str, optional): Caminho do arquivo da imagem a ser salva. Default é 'grafo.png'.
    """
    posicao_nos = nx.circular_layout(grafo)
    pesos = nx.get_edge_attributes(grafo, 'peso')

    plt.figure(figsize=(10, 10))
    nx.draw(grafo, posicao_nos, with_labels=True, node_color='skyblue', node_size=500, edge_color='gray')
    nx.draw_networkx_edge_labels(grafo, posicao_nos, edge_labels=pesos)
    
    plt.title(f"Grafo aleatório com {grafo.number_of_nodes()} nós")
    plt.savefig(caminho_imagem, format='png', dpi=300)
    plt.close()

def salvar_csv_grafo(grafo: nx.Graph, caminho_csv: str = "grafo.csv"):
    """
    Salva os dados do grafo em um arquivo CSV.

    Args:
        grafo (nx.Graph): Grafo a ser salvo.
        caminho_csv (str, optional): Caminho do arquivo CSV. Default é 'grafo.csv'.
    """
    with open(caminho_csv, mode='w', newline='') as arquivo_csv:
        escritor_csv = csv.writer(arquivo_csv)
        escritor_csv.writerow(['no_origem', 'no_destino', 'peso'])
        
        for no_origem, no_destino, dados_aresta in grafo.edges(data=True):
            escritor_csv.writerow([no_origem, no_destino, dados_aresta['peso']])

def main(quantidade_nos: int = 5, probabilidade_conexao: float = 0.3, caminho_pasta: str = "graph", peso_minimo: int = 1, peso_maximo: int = 10):
    """
    Executa o processo de geração do grafo e salva a imagem e os dados em arquivos.

    Args:
        quantidade_nos (int, optional): Número de nós do grafo. Default é 5.
        probabilidade_conexao (float, optional): Probabilidade de conexão entre os nós. Default é 0.3.
        caminho_pasta (str, optional): Caminho da pasta onde os arquivos serão salvos. Default é 'graph'.
        peso_minimo (int, optional): Peso mínimo das arestas. Default é 1.
        peso_maximo (int, optional): Peso máximo das arestas. Default é 10.
    """

    os.makedirs(caminho_pasta, exist_ok=True)

    grafo = gerar_grafo_aleatorio(quantidade_nos, probabilidade_conexao, peso_minimo, peso_maximo)
    
    caminho_imagem = f"{caminho_pasta}/grafo.png"
    salvar_imagem_grafo(grafo, caminho_imagem)
    
    caminho_csv = f"{caminho_pasta}/grafo.csv"
    salvar_csv_grafo(grafo, caminho_csv)

if __name__ == '__main__':
    main()