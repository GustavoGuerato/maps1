from flask import Flask, request, jsonify, send_from_directory
import heapq
import asyncio
import aiohttp
from flask_cors import CORS
import os  # Para usar variáveis de ambiente

app = Flask(__name__)
CORS(app)

# URLs das APIs
API_COORDENADAS = "https://googlelatlog.azurewebsites.net/api/http_trigger?code=_Ka380mEoqT2bUQWBiG8olL2phzfPJPpJLZGp375kLCiAzFuouiTNw%3D%3D"
API_DISTANCIA = "https://googlelatlog.azurewebsites.net/api/get_distancia?code=_Ka380mEoqT2bUQWBiG8olL2phzfPJPpJLZGp375kLCiAzFuouiTNw%3D%3D"

# Cache para coordenadas e distâncias
cache_coordenadas = {}
cache_distancias = {}


async def obter_coordenadas(cidade):
    """Obtém as coordenadas de uma cidade usando a API."""
    if cidade in cache_coordenadas:
        return cache_coordenadas[cidade]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_COORDENADAS, json={"endereco": cidade}
            ) as response:
                if response.status == 200:
                    coordenadas = await response.json()
                    if not coordenadas.get("Latitude") or not coordenadas.get(
                        "Longitude"
                    ):
                        raise ValueError(
                            f"Coordenadas inválidas para {cidade}: {coordenadas}"
                        )
                    cache_coordenadas[cidade] = coordenadas
                    return coordenadas
                else:
                    raise Exception(
                        f"Erro ao obter coordenadas para {cidade}: {response.status}"
                    )
    except Exception as e:
        raise Exception(f"Falha ao obter coordenadas: {e}")


async def calcular_distancia(p1, p2):
    """Calcula a distância entre dois pontos usando a API."""
    key = (p1["Latitude"], p1["Longitude"], p2["Latitude"], p2["Longitude"])
    if key in cache_distancias:
        return cache_distancias[key]

    payload = {
        "p1Lat": p1["Latitude"],
        "p1Lng": p1["Longitude"],
        "p2Lat": p2["Latitude"],
        "p2Lng": p2["Longitude"],
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_DISTANCIA, json=payload) as response:
                if response.status == 200:
                    distancia = (await response.json()).get("Distancia")
                    if distancia is None:
                        raise ValueError("Resposta inválida ao calcular distância")
                    cache_distancias[key] = distancia
                    return distancia
                else:
                    raise Exception(f"Erro ao calcular distância: {response.status}")
    except Exception as e:
        raise Exception(f"Falha ao calcular distância: {e}")


async def inicializar_grafo(cidades):
    """Inicializa o grafo de cidades com distâncias entre elas."""
    grafo = {}
    coordenadas = {}

    # Obtém as coordenadas de todas as cidades
    try:
        coordenadas_resultados = await asyncio.gather(
            *[obter_coordenadas(cidade) for cidade in cidades]
        )
        for cidade, coord in zip(cidades, coordenadas_resultados):
            coordenadas[cidade] = coord
    except Exception as e:
        raise Exception(f"Erro ao inicializar coordenadas: {e}")

    # Calcula as distâncias entre todas as cidades
    async def calcular_distancia_para_cidade(cidade_origem):
        grafo[cidade_origem] = {}
        distancias = await asyncio.gather(
            *[
                calcular_distancia(
                    coordenadas[cidade_origem], coordenadas[cidade_destino]
                )
                for cidade_destino in cidades
                if cidade_origem != cidade_destino
            ]
        )
        for cidade_destino, distancia in zip(cidades, distancias):
            if cidade_origem != cidade_destino:
                grafo[cidade_origem][cidade_destino] = distancia

    try:
        await asyncio.gather(
            *[calcular_distancia_para_cidade(cidade) for cidade in cidades]
        )
    except Exception as e:
        raise Exception(f"Erro ao calcular distâncias: {e}")

    return grafo


def dijkstra(grafo, origem, destino):
    """Implementação do algoritmo de Dijkstra."""
    distancias = {cidade: float("inf") for cidade in grafo}
    distancias[origem] = 0
    pq = [(0, origem)]
    predecessores = {}

    while pq:
        distancia_atual, cidade_atual = heapq.heappop(pq)
        if distancia_atual > distancias[cidade_atual]:
            continue

        for vizinho, peso in grafo[cidade_atual].items():
            nova_distancia = distancia_atual + peso
            if nova_distancia < distancias[vizinho]:
                distancias[vizinho] = nova_distancia
                predecessores[vizinho] = cidade_atual
                heapq.heappush(pq, (nova_distancia, vizinho))

    caminho = []
    cidade_atual = destino
    while cidade_atual != origem:
        caminho.insert(0, cidade_atual)
        cidade_atual = predecessores.get(cidade_atual)
        if cidade_atual is None:
            return None, None
    caminho.insert(0, origem)
    return caminho, distancias[destino]

@app.route('/')
def serve_index():
    """Serve o arquivo index.html"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/calcular-rota", methods=["POST"])
async def calcular_rota():
    """Endpoint para calcular a melhor rota entre duas cidades."""
    dados = request.json
    origem = dados["origem"]
    destino = dados["destino"]

    cidades = [
        "Santo André",
        "São Bernardo",
        "São Caetano",
        "Mauá",
        "Ribeirão Pires",
        "Diadema",
        "São Paulo",
        "Guarulhos",
        "Campinas",
        "São Vicente",
        "Jundiaí",
        "Sorocaba",
        "Osasco",
        "Barueri",
        "Arujá",
        "Carapicuíba",
        "Cotia",
        "Embu das Artes",
        "Itapevi",
        "Mogi das Cruzes",
        "Itaquaquecetuba",
        "Ferraz de Vasconcelos",
    ]

    try:
        grafo = await inicializar_grafo(cidades)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    caminho, distancia = dijkstra(grafo, origem, destino)

    if caminho and len(caminho) > 2:
        return jsonify({"caminho": caminho, "distancia": distancia, "grafo": grafo})
    elif caminho:
        for cidade in cidades:
            if cidade not in caminho:
                caminho1, distancia1 = dijkstra(grafo, origem, cidade)
                caminho2, distancia2 = dijkstra(grafo, cidade, destino)
                if caminho1 and caminho2:
                    caminho_intermediario = caminho1[:-1] + caminho2
                    distancia_total = distancia1 + distancia2
                    return jsonify(
                        {
                            "caminho": caminho_intermediario,
                            "distancia": distancia_total,
                            "grafo": grafo,
                        }
                    )

    return (
        jsonify(
            {"erro": "Caminho não encontrado com pelo menos uma cidade intermediária."}
        ),
        404,
    )


if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 5000))  # Porta padrão para produção
    app.run(host=host, port=port)
