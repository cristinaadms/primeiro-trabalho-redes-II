#!/bin/bash

# Função para obter o IP da interface padrão (eth0)
get_ip() {
    ip addr show eth0 | awk '/inet / {print $2}' | cut -d/ -f1
}

# Função para calcular o gateway (supondo que termina com .2)
calculate_gateway() {
    local ip=$1
    IFS='.' read -r o1 o2 o3 o4 <<< "$ip"
    echo "$o1.$o2.$o3.2"
}

# Obtemos o IP e o gateway
IP=$(get_ip)
GATEWAY=$(calculate_gateway "$IP")

# Atualiza a rota padrão
ip route delete default 2>/dev/null
ip route add default via "$GATEWAY"

echo "Gateway padrão configurado para $GATEWAY"

# Mantém o container vivo indefinidamente
sleep infinity
