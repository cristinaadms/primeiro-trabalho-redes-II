# HeLSA – Simulação de Topologia de Rede com Pacotes Hello e LSA

## Descrição

Este projeto simula uma rede composta por roteadores e hosts interligados em sub-redes. Seu objetivo é verificar a conectividade entre os roteadores e seus respectivos hosts utilizando pacotes Hello e LSA (Link State Advertisement), seguidos pela aplicação do algoritmo de Dijkstra para cálculo das rotas mais curtas. Os roteadores inicialmente desconhecem a topologia da rede e, por meio da troca de mensagens, constroem suas tabelas de roteamento. Após o processo, é possível testar a comunicação entre quaisquer dois hosts da rede, validando a eficiência do roteamento.

## Objetivo do Projeto

Este projeto foi desenvolvido para a primeira avaliação da disciplina Redes de Computadores II. Seu objetivo principal é aplicar conceitos teóricos vistos em aula, como protocolos de comunicação, topologias de rede e simulação de roteadores, em uma implementação prática. 

## Justificativa do Protocolo Escolhido

O UDP (User Datagram Protocol) é o protocolo utilizado neste projeto. Trata-se de um protocolo da camada de transporte do modelo TCP/IP que envia dados em forma de datagramas, sem garantias de entrega, o que pode representar uma desvantagem. No entanto, por oferecer maior velocidade de transmissão, o UDP é ideal para cenários em que a baixa latência é importante. A escolha se justifica pela natureza da aplicação simulada: a troca rápida de mensagens entre roteadores para descoberta de vizinhos e propagação de pacotes LSA. Nesse contexto, a leveza do UDP atende à necessidade de um protocolo eficiente para disseminar rapidamente informações sobre a topologia da rede.

## Como a topologia foi construída

A topologia da rede utilizada neste projeto foi gerada automaticamente por meio de um script que utiliza a biblioteca NetworkX. O grafo é criado de forma aleatória com base no modelo de Erdős-Rényi, onde a conexão entre dois nós ocorre com uma determinada probabilidade. O processo é executado pela função gerar_grafo_aleatorio, que também atribui pesos aleatórios às arestas, simulando os custos de comunicação entre os roteadores. Para garantir que todos os nós estejam conectados, o algoritmo verifica se o grafo gerado é conexo; caso contrário, adiciona arestas até que essa condição seja satisfeita. Cada nó recebe um rótulo no formato rt0, rt1, etc., representando diferentes roteadores, e cada aresta recebe um peso correspondente, que será utilizado pelo algoritmo de Dijkstra. Após a geração da topologia, uma visualização gráfica do grafo é salva como imagem PNG, junto com um arquivo CSV contendo os nós de origem, destino e seus respectivos pesos, ambos armazenados em uma pasta para uso em simulações posteriores.

## Principais Ferramentas Utilizadas

- **NetworkX:** Criação e análise do grafo de rede
- **Matplotlib:** Visualização gráfica da topologia
- **psutil:** Monitoramento de recursos do sistema
- **Docker Compose:** Orquestração dos serviços em contêineres



## Execução do Projeto

Para executar o projeto, siga os passos abaixo:

Abra o Docker Desktop.

Execute o arquivo build_graph.py para gerar o grafo em formato PNG e CSV.

Execute o arquivo build_compose.py para gerar o arquivo docker-compose.yml.

No terminal, baixe a imagem oficial do Python 3.13.2 slim com o comando:

```bash
docker pull python:3.13.2-slim
```

Execute o comando para iniciar e construir os containers:
```bash
docker-compose up --build
```


Para usar o comando ping, acesse o Docker pelo VSCode e escolha um roteador ou host:
Ping de roteador para roteador:
```bash
ping <IP do roteador de destino>
```
Ping de host para host:
```bash
ping <IP do host de destino>
```


Para usar o comando traceroute, também via Docker no VSCode, escolha um roteador ou host:
Traceroute de roteador para roteador:
```bash
traceroute <IP do roteador de destino>
```
Traceroute de host para host:
```bash
traceroute <IP do host de destino>
```


Para parar a execução, pressione Ctrl + C e depois execute:
```bash
docker-compose down
```

