#!/usr/bin/env python3
"""
Deploy Cloudflare Worker for Gram Network Miner
=================================================
Creates a Cloudflare Worker that proxies Gram Network API requests.
Bypasses cloud IP restrictions (AWS, GCP, Azure get HTTP 403).

Usage:
  python3 deploy_worker.py

Requirements:
  pip3 install requests

You need:
  - Cloudflare account (free): https://dash.cloudflare.com
  - API Token with "Workers Scripts > Edit" permission
  - Account ID (from dashboard URL)
"""

import requests
import json
import sys
import os

WORKER_CODE = r"""export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type'
        }
      });
    }
    
    const endpoint = url.searchParams.get('endpoint');
    const initData = url.searchParams.get('initData');
    
    if (!endpoint || !initData) {
      return new Response(JSON.stringify({ error: 'params missing: endpoint, initData' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }
    
    const targetUrl = 'https://app.gramnetwork.online/api/' + endpoint + '.php';
    const postEndpoints = ['start_mining', 'claim_mining', 'claim_daily', 'click'];
    const isPost = postEndpoints.includes(endpoint);
    
    try {
      const fetchOpts = {
        method: isPost ? 'POST' : 'GET',
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
          'Accept': 'application/json, text/plain, */*',
          'Referer': 'https://app.gramnetwork.online/',
          'Origin': 'https://app.gramnetwork.online'
        }
      };
      
      let finalUrl;
      if (isPost) {
        fetchOpts.headers['Content-Type'] = 'application/x-www-form-urlencoded';
        fetchOpts.body = 'initData=' + encodeURIComponent(initData);
        finalUrl = targetUrl;
      } else {
        finalUrl = targetUrl + '?initData=' + encodeURIComponent(initData);
      }
      
      const apiRes = await fetch(finalUrl, fetchOpts);
      const body = await apiRes.text();
      return new Response(body, {
        status: apiRes.status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 502,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }
  }
};"""

WORKER_NAME = "gram-network-proxy"


def verify_token(api_token):
    headers = {"Authorization": f"Bearer {api_token}"}
    r = requests.get("https://api.cloudflare.com/client/v4/user/tokens/verify", headers=headers)
    return r.json().get("success", False)


def get_subdomain(account_id, api_token):
    headers = {"Authorization": f"Bearer {api_token}"}
    r = requests.get(f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/subdomain", headers=headers)
    if r.json().get("success"):
        return r.json()["result"]["subdomain"]
    return None


def create_subdomain(account_id, api_token, subdomain):
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    r = requests.put(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/subdomain",
        headers=headers,
        json={"subdomain": subdomain}
    )
    return r.json().get("success", False)


def deploy_worker(account_id, api_token):
    boundary = "----GramMinerDeploy"
    metadata = json.dumps({"main_module": "worker.js", "bindings": []})
    part1 = f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\nContent-Type: application/json\r\n\r\n{metadata}'
    part2 = f'--{boundary}\r\nContent-Disposition: form-data; name="worker.js"; filename="worker.js"\r\nContent-Type: application/javascript+module\r\n\r\n{WORKER_CODE}'
    body = part1 + '\r\n' + part2 + f'\r\n--{boundary}--\r\n'
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{WORKER_NAME}"
    r = requests.put(url, headers=headers, data=body.encode('utf-8'))
    return r.json()


def main():
    print("=" * 50)
    print("Gram Network - Cloudflare Worker Deployer")
    print("=" * 50)
    print()

    account_id = input("Cloudflare Account ID: ").strip()
    api_token = input("Cloudflare API Token: ").strip()

    if not account_id or not api_token:
        print("ERROR: Account ID and API Token are required!")
        sys.exit(1)

    print("\nVerifying API token...")
    if not verify_token(api_token):
        print("ERROR: Invalid API token!")
        print("Create one at: https://dash.cloudflare.com/profile/api-tokens")
        print("Permission: Account > Workers Scripts > Edit")
        sys.exit(1)
    print("Token valid!")

    print("\nChecking workers.dev subdomain...")
    subdomain = get_subdomain(account_id, api_token)
    if not subdomain:
        print("No subdomain found. Creating one...")
        new_sub = input("Enter desired subdomain (e.g. yourname): ").strip()
        if create_subdomain(account_id, api_token, new_sub):
            subdomain = new_sub
        else:
            print("ERROR: Could not create subdomain!")
            sys.exit(1)
    print(f"Subdomain: {subdomain}.workers.dev")

    print(f"\nDeploying worker '{WORKER_NAME}'...")
    result = deploy_worker(account_id, api_token)

    if result.get("success"):
        worker_url = f"https://{WORKER_NAME}.{subdomain}.workers.dev"
        print(f"\n{'=' * 50}")
        print(f"Worker deployed!")
        print(f"URL: {worker_url}")
        print(f"{'=' * 50}")

        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            config["worker_url"] = worker_url
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"\nconfig.json updated automatically!")
        else:
            print(f"\nAdd this to config.json:")
            print(f'  "worker_url": "{worker_url}"')
    else:
        print(f"\nERROR: Deploy failed!")
        print(json.dumps(result.get("errors", []), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
