"""Comprueba que las tres claves responden. Antes de construir, no despues."""
import json, os, urllib.error, urllib.request
from pathlib import Path

for linea in Path(".env").read_text(encoding="utf-8").splitlines():
    if "=" in linea and not linea.startswith("#"):
        k, _, v = linea.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

def pedir(url, datos=None, cabeceras=None, metodo=None):
    r = urllib.request.Request(url, data=datos, headers=cabeceras or {},
                               method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read()[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400]
    except Exception as e:
        return 0, str(e)[:200].encode()

print("SerpApi        ", end="", flush=True)
c, cuerpo = pedir("https://serpapi.com/search.json?q=api+world+hackathon&num=1"
                  f"&api_key={os.environ['SERPAPI_KEY']}")
print(c, "OK" if c == 200 else cuerpo[:180])

print("Nutrient DWS   ", end="", flush=True)
c, cuerpo = pedir("https://api.nutrient.io/account/info",
                  cabeceras={"Authorization": f"Bearer {os.environ['NUTRIENT_KEY']}"})
print(c, cuerpo[:200])

print("Foxit          ", end="", flush=True)
c, cuerpo = pedir(
    "https://na1.fusion.foxit.com/pdf-services/api/documents/enable",
    cabeceras={"client_id": os.environ["FOXIT_CLIENT_ID"],
               "client_secret": os.environ["FOXIT_CLIENT_SECRET"]})
print(c, cuerpo[:200])
