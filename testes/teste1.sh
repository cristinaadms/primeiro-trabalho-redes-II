#realização do ping somente entre os roteadores

#!/bin/bash

# Dicionários e lista
declare -A ip_para_container
declare -A roteadores_unicos
lista_roteadores=()

# Contadores
sucessos=0
falhas=0

# Lê o arquivo docker-compose.yml e extrai IPs e nomes dos contêineres
while read -r linha; do
  if [[ $linha == *"container_name:"* ]]; then
    nome_container=$(echo "$linha" | awk '{print $2}')
  elif [[ $linha == *"ipv4_address:"* ]]; then
    ip_container=$(echo "$linha" | awk '{print $2}')
    ip_para_container["$ip_container"]=$nome_container

    # Identifica roteadores e os adiciona à lista
    if [[ "$nome_container" =~ ^r[0-9]+$ ]] && [[ -z "${roteadores_unicos[$nome_container]}" ]]; then
      lista_roteadores+=("$nome_container")
      roteadores_unicos["$nome_container"]=1
    fi
  fi
done < docker-compose.yml

# Cabeçalho
echo "============================================="
echo "Verificação de Conectividade entre Roteadores"
echo "============================================="

# Testa conectividade entre roteadores (somente entre roteadores)
for roteador_origem in "${lista_roteadores[@]}"; do
  echo -e "\nTestando a partir do roteador: $roteador_origem"
  for roteador_destino in "${lista_roteadores[@]}"; do
    # Ignora o próprio roteador
    if [[ "$roteador_origem" == "$roteador_destino" ]]; then
      continue
    fi

    # Executa o ping e contabiliza os resultados
    printf "Ping para %-15s (contêiner: %-10s)... " "$roteador_destino" "$roteador_destino"
    ip_destino=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$roteador_destino")

    if docker exec "$roteador_origem" ping -c 1 -W 1 "$ip_destino" &> /dev/null; then
      echo "Sucesso"
      ((sucessos++))
    else
      echo "Falha"
      ((falhas++))
    fi
  done
  echo "-------------------------------------------------------------"
done

# Relatório final
total_testes=$((sucessos + falhas))

echo -e "\nRelatório de Conectividade:"
echo "Total de testes realizados : $total_testes"
echo "Respostas bem-sucedidas    : $sucessos"
echo "Respostas com falha        : $falhas"

if ((total_testes > 0)); then
  percentual_perda=$((100 * falhas / total_testes))
  echo "Taxa de perda              : $percentual_perda%"
else
  echo "Taxa de perda              : N/A"
fi
