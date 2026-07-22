import project_utils as pu


info = pu.build_tree()
info += pu.gerar_indice()
info += pu.carregar_projeto()

print (info)





