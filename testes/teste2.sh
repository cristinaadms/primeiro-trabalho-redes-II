#!/bin/bash

# Lista de contêineres "host" e "roteadores"
containers_hosts=()
containers_roteadores=()

# Dicionário para armazenar mapeamento de IP -> nome do contêiner
declare -A ip_para_nome

# Contadores de sucesso e falha
contagem_sucessos=0
contagem_falhas=0

# Leitura do arquivo docker-compose.yml
while read -r linha; do
  if [[ $linha == *"container_name:"* ]]; then
    nome_container=$(echo $linha | awk '{print $2}')
  fi
  if [[ $linha == *"ipv4_address:"* ]]; then
    ip=$(echo $linha | awk '{print $2}')
    ip_para_nome[$ip]=$nome_container

    # Adiciona contêineres "host" à lista
    if [[ "$nome_container" == *_h* ]]; then
      containers_hosts+=("$nome_container")
    # Adiciona contêineres "roteador" à lista (aqui estamos usando "_r" como convenção para roteadores)
    elif [[ "$nome_container" == *_r* ]]; then
      containers_roteadores+=("$nome_container")
    fi
  fi
done < docker-compose.yml

# Filtra os IPs que pertencem aos contêineres "host"
ips_hosts=()
for ip in "${!ip_para_nome[@]}"; do
  nome_container="${ip_para_nome[$ip]}"
  if [[ " ${containers_hosts[@]} " =~ " ${nome_container} " ]]; then
    ips_hosts+=("$ip")
  fi
done

# Exibe cabeçalho
echo "================================================"
echo "Teste de Conectividade entre Roteadores"
echo "================================================"

# Loop de testes de ping entre os roteadores
for origem in "${containers_roteadores[@]}"; do
  echo -e "\nIniciando pings entre roteador: $origem"

  for destino in "${containers_roteadores[@]}"; do
    # Ignora o ping para o próprio roteador
    if [[ "$origem" == "$destino" ]]; then
      continue
    fi

    ip_destino="${ip_para_nome[$(echo $destino | awk '{print $2}')]}"

    # Realiza o ping entre os roteadores
    printf "Pingando roteador %-15s (Contêiner: %-15s)... " "$ip_destino" "$destino"
    if docker exec "$origem" ping -c 1 -W 1 "$ip_destino" &> /dev/null; then
      echo "Conectividade bem-sucedida"
      ((contagem_sucessos++))
    else
      echo "Falha na conectividade"
      ((contagem_falhas++))
    fi
  done
  echo "---------------------------------------------"
done

# Exibe cabeçalho para a verificação entre os hosts
echo "================================================"
echo "Teste de Conectividade entre Contêineres Hosts"
echo "================================================"

# Loop de testes de ping entre os hosts
for origem in "${containers_hosts[@]}"; do
  echo -e "\nIniciando pings a partir do contêiner: $origem"

  for ip_destino in "${ips_hosts[@]}"; do
    nome_destino="${ip_para_nome[$ip_destino]}"

    # Ignora o ping para o próprio contêiner
    if [[ "$origem" == "$nome_destino" ]]; then
      continue
    fi

    # Realiza o ping entre os hosts
    printf "Pingando IP %-15s (Contêiner: %-15s)... " "$ip_destino" "$nome_destino"
    if docker exec "$origem" ping -c 1 -W 1 "$ip_destino" &> /dev/null; then
      echo "Conectividade bem-sucedida"
      ((contagem_sucessos++))
    else
      echo "Falha na conectividade"
      ((contagem_falhas++))
    fi
  done
  echo "---------------------------------------------"
done

# Cálculo das estatísticas finais
total_testes=$((contagem_sucessos + contagem_falhas))
echo -e "\nResumo Final de Testes de Conectividade:"
echo "Total de Testes Realizados: $total_testes"
echo "Conectividade Bem-Sucedida: $contagem_sucessos"
echo "Falhas na Conectividade: $contagem_falhas"

if ((total_testes > 0)); then
  percentual_perda=$((100 * contagem_falhas / total_testes))
  echo "Taxa de Perda de Pacotes: $percentual_perda%"
else
  echo "Taxa de Perda de Pacotes: N/A"
fi
