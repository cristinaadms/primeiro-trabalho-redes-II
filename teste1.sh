#!/bin/bash

# Cores para melhor visualização
VERDE='\033[0;32m'
VERMELHO='\033[0;31m'
AMARELO='\033[1;33m'
RESET='\033[0m'

# Armazena informações sobre roteadores e suas redes
declare -A roteador_redes
declare -A rede_roteadores
lista_roteadores=()

echo -e "${AMARELO}Coletando informações de rede dos roteadores...${RESET}"

# Para cada roteador, obtenha as redes e IPs relevantes (ignorando redes host)
for container in $(docker ps --format '{{.Names}}' | grep "^rt[0-9]\+$"); do
  lista_roteadores+=("$container")
  echo "Processando roteador: $container"
  
  # Lista todas as redes do container
  networks_json=$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$container")
  
  # Extrair nomes de rede e IPs usando jq, se disponível, ou fallback para grep/awk
  if command -v jq &> /dev/null; then
    # Usa jq para extrair informações
    network_data=$(echo "$networks_json" | jq -r 'to_entries[] | select(.key | test("hosts_net") | not) | "\(.key)|\(.value.IPAddress)"')
  else
    # Fallback para grep/awk/sed se jq não estiver disponível
    network_data=$(echo "$networks_json" | 
      grep -o '"[^"]*_net":{[^}]*"IPAddress":"[^"]*"' | 
      grep -v "hosts_net" | 
      sed -E 's/.*"([^"]*)":\{.*"IPAddress":"([^"]*)".*/\1|\2/')
  fi
  
  # Processa os dados extraídos
  while IFS= read -r net_info; do
    if [[ -z "$net_info" ]]; then
      continue
    fi
    
    network_name=$(echo "$net_info" | cut -d'|' -f1)
    ip_address=$(echo "$net_info" | cut -d'|' -f2)
    
    # Armazena somente redes entre roteadores (ignorando redes hosts_net)
    if [[ "$network_name" != *"hosts_net"* && ! -z "$ip_address" ]]; then
      roteador_redes["${container}|${network_name}"]=$ip_address
      
      # Armazena quais roteadores estão em cada rede
      if [[ -z "${rede_roteadores[$network_name]}" ]]; then
        rede_roteadores["$network_name"]="$container"
      else
        rede_roteadores["$network_name"]="${rede_roteadores[$network_name]} $container"
      fi
    fi
  done <<< "$network_data"
done

# Cabeçalho
echo -e "\n${AMARELO}=============================================${RESET}"
echo -e "${AMARELO}Verificação de Conectividade entre Roteadores${RESET}"
echo -e "${AMARELO}=============================================${RESET}"

# Contadores
sucessos=0
falhas=0
total_pings=0

# Para cada par de roteadores, tente encontrar uma rota
for origem in "${lista_roteadores[@]}"; do
  echo -e "\n${AMARELO}Testando a partir do roteador: $origem${RESET}"
  
  for destino in "${lista_roteadores[@]}"; do
    # Ignora o próprio roteador
    if [[ "$origem" == "$destino" ]]; then
      continue
    fi
    
    # Encontre uma rede comum entre origem e destino
    rede_comum=""
    ip_destino=""
    
    # Verifique cada rede do roteador de origem
    for chave in "${!roteador_redes[@]}"; do
      roteador=$(echo "$chave" | cut -d'|' -f1)
      rede=$(echo "$chave" | cut -d'|' -f2)
      
      if [[ "$roteador" == "$origem" ]]; then
        # Verifique se o destino está nesta rede
        roteadores_na_rede="${rede_roteadores[$rede]}"
        if [[ "$roteadores_na_rede" == *"$destino"* ]]; then
          rede_comum="$rede"
          # Encontre o IP do destino nesta rede
          ip_destino="${roteador_redes[${destino}|${rede}]}"
          break
        fi
      fi
    done
    
    printf "Ping para %-15s ... " "$destino"
    
    if [[ -z "$ip_destino" ]]; then
      # Não há conexão direta, use qualquer IP do destino
      # (na prática o roteamento deveria funcionar se configurado corretamente)
      for chave in "${!roteador_redes[@]}"; do
        roteador=$(echo "$chave" | cut -d'|' -f1)
        if [[ "$roteador" == "$destino" ]]; then
          ip_destino="${roteador_redes[$chave]}"
          break
        fi
      done      
      echo -ne "${AMARELO}[Rota Indireta]${RESET} "
    else
      echo -ne "${AMARELO}[Rede: $rede_comum]${RESET} "
    fi
    
    # Executa o ping
    ((total_pings++))
    if docker exec "$origem" ping -c 1 -W 1 "$ip_destino" > /dev/null 2>&1; then
      echo -e "${VERDE}Sucesso${RESET} (IP: $ip_destino)"
      ((sucessos++))
    else
      echo -e "${VERMELHO}Falha${RESET} (IP: $ip_destino)"
      ((falhas++))
    fi
  done
  echo -e "${AMARELO}-------------------------------------------------------------${RESET}"
done

# Relatório final
echo -e "\n${AMARELO}Relatório de Conectividade:${RESET}"
echo "Total de testes realizados : $total_pings"
echo -e "Respostas bem-sucedidas    : ${VERDE}$sucessos${RESET}"
echo -e "Respostas com falha        : ${VERMELHO}$falhas${RESET}"

if ((total_pings > 0)); then
  percentual_perda=$((100 * falhas / total_pings))
  echo -e "Taxa de perda              : ${AMARELO}$percentual_perda%${RESET}"
else
  echo "Taxa de perda              : N/A"
fi

# Imprime detalhes sobre as redes e conexões
echo -e "\n${AMARELO}Detalhes das Redes Entre Roteadores:${RESET}"
for rede in "${!rede_roteadores[@]}"; do
  if [[ "$rede" != *"hosts"* ]]; then
    echo -e "${AMARELO}Rede: $rede${RESET}"
    for roteador in ${rede_roteadores[$rede]}; do
      ip="${roteador_redes[${roteador}|${rede}]}"
      echo "  - $roteador: $ip"
    done
    echo ""
  fi
done