import requests
import os
import zipfile

def download_svf_bundle(urn, access_token):
    base_url = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/{urn}/manifest"
    headers = {
        'Authorization': f'Bearer {access_token}',
    }

    # Fetch the manifest data
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch manifest: {response.status_code}")
        return

    manifest_data = response.json()
    svf_urns = []

    # Parse the manifest for SVF URNs
    derivatives = manifest_data.get('derivatives', [])
    for item in derivatives:
        if "children" in item:
            for child in item["children"]:
                if "children" in child:
                    for sub_child in child["children"]:
                        if sub_child.get("mime") == "application/autodesk-svf":
                            svf_urns.append(sub_child["urn"])

    if not svf_urns:
        print("No SVF URNs found.")
        return

    svf_urn = svf_urns[0]
    svf_url = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/{urn}/manifest/{svf_urn}"
    print(f"Downloading SVF bundle from: {svf_url}")

    # Download the SVF file
    response = requests.get(svf_url, headers=headers, stream=True)
    if response.status_code == 200:
        os.makedirs("svf_bundle", exist_ok=True)
        zip_file_path = "svf_bundle/output.zip"

        with open(zip_file_path, "wb") as svf_file:
            svf_file.write(response.content)

        print("SVF bundle downloaded successfully.")

        # Extract the SVF bundle
        with zipfile.ZipFile(zip_file_path, "r") as archive:
            archive.extractall("svf_bundle")
            print("SVF bundle extracted successfully.")
    else:
        print(f"Failed to download SVF bundle: {response.status_code}")

# Replace with your URN and Access Token
urn = "dXJuOmFkc2sub2JqZWN0czpvcy5vYmplY3Q6aW50ZWNoX2xhdHRpY2VfZGVtby9ncmlwcGVyX2FybV85YTA2ZjFiNC01YWE3LTQ5ZTYtYWRiOC0yNWFhMDU2ODZmNjkuc3RlcA=="
access_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6IlhrUFpfSmhoXzlTYzNZS01oRERBZFBWeFowOF9SUzI1NiIsInBpLmF0bSI6ImFzc2MifQ.eyJzY29wZSI6WyJkYXRhOnJlYWQiXSwiY2xpZW50X2lkIjoiVGY0dU9Zc3ZNVjN4RWpBOHVpUUg1QWlYV01YR290Nm4xWFp5cGhFTFRKV1BxNHN6IiwiaXNzIjoiaHR0cHM6Ly9kZXZlbG9wZXIuYXBpLmF1dG9kZXNrLmNvbSIsImF1ZCI6Imh0dHBzOi8vYXV0b2Rlc2suY29tIiwianRpIjoiSHlQcUhYWUVJVnZGNHp1OEFEZHg1NWZ4VU1SVndIUjVTcjYzeGdDVkx6VFJQUk56ZmtPWFZndVphQWFHY2wyZiIsImV4cCI6MTczNjMxNjYzN30.e6wf69t3bpDctHpSNwZ72lBJ6x587PElIsU6mbEMi5RkV_QcYy_61110U6d1lsyM91MVf-Da9c_ws_BHl4W5s_r94eaUIUffdzGrwYC98G9YeAY01liP0wiZ6jKZz7YrDZzqfIedkML1uligPvHemPTudsInNmcICrkhL6aYkuSqQR5dyeM34BF_QNGNGRZtYuHiR5eVYx2n6htXyofLrdkDmz5z7cV6bv1T1R2xDMImvevICcjPDq4NWM6x2NOeIy9fUGqRNW5rZkTvREJJj1bCBTzpfmdfYbK899n7-3MRMOybCmRfmC7Fm6lYQR7eTT3WHwuktyB3l7niDMiYKQ"
download_svf_bundle(urn, access_token)
