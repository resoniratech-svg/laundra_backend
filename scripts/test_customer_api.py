import requests

def main():
    url = "http://localhost:8000/api/v1/prepaid-packages/customer/6adbdf18-4621-40c5-b446-13c275b4189e"
    print(f"Calling GET {url}...")
    try:
        res = requests.get(url)
        print("Status code:", res.status_code)
        print("Response JSON:", res.text)
    except Exception as e:
        print("Error calling endpoint:", e)

if __name__ == "__main__":
    main()
