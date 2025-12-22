import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================
# CONFIGURATION
# ==========================
ENDPOINT_URL = "http://3.111.177.75/api/messages-public"
TOTAL_REQUESTS = 100        # Total requests to send
CONCURRENCY = 100            # Number of parallel threads
REQUEST_TIMEOUT = 200          # seconds

HEADERS = {
    "Content-Type": "application/json"
}

# ==========================
# LOAD INPUT DATA
# ==========================
def load_list_from_file(file_path):
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip()]

emails = load_list_from_file("./json_repo/emails.txt")
questions = load_list_from_file("./json_repo/questions.txt")

# ==========================
# REQUEST FUNCTION
# ==========================
def send_request(request_id):
    email = random.choice(emails)
    question = random.choice(questions)

    payload = {
        "email": email,
        "sender" : "user",
        "text": question
    }

    start_time = time.time()
    try:
        response = requests.post(
            ENDPOINT_URL,
            json=payload,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )
        latency = time.time() - start_time

        return {
            "request_id": request_id,
            "status_code": response.status_code,
            "latency": latency
        }

    except requests.exceptions.RequestException as e:
        return {
            "request_id": request_id,
            "status_code": "ERROR",
            "error": str(e)
        }

# ==========================
# MAIN LOAD TEST RUNNER
# ==========================
def run_load_test():
    print(f"Starting load test:")
    print(f"- Endpoint: {ENDPOINT_URL}")
    print(f"- Total Requests: {TOTAL_REQUESTS}")
    print(f"- Concurrency: {CONCURRENCY}\n")

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [
            executor.submit(send_request, i)
            for i in range(TOTAL_REQUESTS)
        ]

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            if result.get("status_code") == "ERROR":
                print(f"[ERROR] Req {result['request_id']}: {result['error']}")
            else:
                print(
                    f"[OK] Req {result['request_id']} "
                    f"Status={result['status_code']} "
                    f"Latency={result['latency']:.2f}s"
                )

    total_time = time.time() - start_time

    # ==========================
    # SUMMARY
    # ==========================
    success_count = len([r for r in results if r.get("status_code") != "ERROR"])
    error_count = TOTAL_REQUESTS - success_count
    avg_latency = sum(
        r["latency"] for r in results if "latency" in r
    ) / max(success_count, 1)

    print("\n===== LOAD TEST SUMMARY =====")
    print(f"Total Time      : {total_time:.2f}s")
    print(f"Successful Req  : {success_count}")
    print(f"Failed Req      : {error_count}")
    print(f"Avg Latency     : {avg_latency:.2f}s")
    print(f"Throughput      : {TOTAL_REQUESTS / total_time:.2f} req/sec")

if __name__ == "__main__":
    run_load_test()
