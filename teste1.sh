#!/bin/bash

# Lista de contêineres roteadores
containers_roteadores=()

# Dicionários
declare -A ip_para_nome
declare -A nome_para_ips  # Mapeia nome -> lista de IPs (em string separada por espaços)

# Contadores
contagem_sucessos=0
contagem_falhas=0

# Leitura do docker-compose.yml
while read -r linha; do
  if [[ $linha == *"container_name:"* ]]; then
    nome_container=$(echo $linha | awk '{print $2}')
  fi
  if [[ $linha == *"ipv4_address:"* ]]; then
    ip=$(echo $linha | awk '{print $2}')
    
    if [[ "$nome_container" =~ ^rt[0-9]+$ ]]; then
      containers_roteadores+=("$nome_container")
      ip_para_nome[$ip]=$nome_container
      nome_para_ips[$nome_container]+="$ip "  # Adiciona IP à lista do container
    fi
  fi
done < docker-compose.yml

# Remover duplicatas da lista de roteadores
containers_roteadores=($(echo "${containers_roteadores[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

# =======================
# Testes entre ROTEADORES
# =======================
echo "================================================"
echo "Teste de Conectividade entre Roteadores"
echo "================================================"

for origem in "${containers_roteadores[@]}"; do
  echo -e "\nIniciando pings a partir do roteador: $origem"

  for destino in "${containers_roteadores[@]}"; do
    if [[ "$origem" == "$destino" ]]; then
      continue
    fi

    # Loop sobre todos os IPs do roteador de destino
    for ip_destino in ${nome_para_ips[$destino]}; do
      printf "Pingando IP %-15s (Contêiner: %-5s)... " "$ip_destino" "$destino"
      if docker exec "$origem" ping -c 1 -W 1 "$ip_destino" &> /dev/null; then
        echo "Conectividade bem-sucedida"
        ((contagem_sucessos++))
      else
        echo "Falha na conectividade"
        ((contagem_falhas++))
      fi
    done
  done
  echo "---------------------------------------------"
done

# =====================
# Resumo final
# =====================
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
