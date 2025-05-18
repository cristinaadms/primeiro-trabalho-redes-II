import matplotlib.pyplot as plt

# Dados coletados
categorias = ['Testes', 'Sucessos', 'Falhas']  # Nomes mais curtos
routers = [52, 52, 0]
hosts = [90, 90, 0]

# Largura das barras e posição
largura = 0.35
x = range(len(categorias))

# Criação do gráfico
fig, ax = plt.subplots()
ax.bar([i - largura/2 for i in x], routers, width=largura, label='Roteadores', color='#666666')
ax.bar([i + largura/2 for i in x], hosts, width=largura, label='Hosts', color='#cccccc')

# Personalização
ax.set_ylabel('Quantidade')
ax.set_title('Comparação de Testes de Conectividade')
ax.set_xticks(x)
ax.set_xticklabels(categorias, fontsize=9)  # Fonte menor nos rótulos do eixo X
ax.legend()

# Adição dos valores acima das barras
for i in x:
    ax.text(i - largura/2, routers[i] + 1, str(routers[i]), ha='center', fontsize=9)
    ax.text(i + largura/2, hosts[i] + 1, str(hosts[i]), ha='center', fontsize=9)

plt.tight_layout()
plt.show()
