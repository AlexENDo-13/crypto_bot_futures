import requests, hashlib, hmac, time, urllib.parse

api_key = "CdSWeAc3nivQLxvBqbX40cGwGi5P9TLboVUl2VvoYQfYMfM8it9WbGCwmtbZG77pYl3rzTVx7hkxTgwkw"
api_secret = "JmF7d48wrEfkkF1WWLS2OSSJmVVvtyzb5mnVmweM2MLqKAyYUwoTJT8FG6SZ8A08qv2Rb6RUZycnGe43PQ"

timestamp = str(int(time.time() * 1000))
params = {"timestamp": timestamp, "recvWindow": "5000"}
sorted_params = sorted(params.items(), key=lambda x: x[0])
query_string = urllib.parse.urlencode(sorted_params)
signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()

url = f"https://open-api.bingx.com/openApi/swap/v2/user/balance?{query_string}&signature={signature}"
headers = {"X-BX-APIKEY": api_key}
resp = requests.get(url, headers=headers)
print(resp.json())
