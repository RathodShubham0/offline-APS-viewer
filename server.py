from flask import Flask, request, jsonify
import requests 
import os
import json
import zipfile
import time
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

# Home route
@app.route("/download_svf_bundle", methods=['POST'])
def download_data():
    res =  request.json

    new_urn = res['model_urn']
    access_token = generate_token()

    base_url = "https://developer.api.autodesk.com/modelderivative/v2/designdata"
    endpoint = f"{base_url}/{new_urn}/manifest"

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        response = requests.get(endpoint, headers=headers)
        manifest_data = response.json()
        status = manifest_data['status']

        print("Status of manifest:", status)

        if status == "success":
            download_svf_file_url(manifest_data, new_urn, access_token, None)
        elif status == "failed":
            print("Manifest processing failed.")
        elif status in ["pending", "inprogress"]:
            time.sleep(10)
            download_data()  # Retry

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
    return "Welcome to the Flask server!"

def generate_token():
    url = "https://developer.api.autodesk.com/authentication/v2/token"
    payload = 'grant_type=client_credentials&scope=data%3Aread'
    headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': 'Basic VGY0dU9Zc3ZNVjN4RWpBOHVpUUg1QWlYV01YR290Nm4xWFp5cGhFTFRKV1BxNHN6OnM5ZVR4Nm54UG1HeTFsQm1LV1VSVHdyaDFvaDJ6ak1laHc3VXhGMG85cThoWE5CdGFFYWN3eGFDQURPSTBGRXc=',
    'Accept': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)
    data1 = response.json()
    access_token = data1.get('access_token')
    return access_token

def download_svf_file_url(manifest_data, new_urn, access_token, file):
    svf_urns = []
    derivatives = manifest_data['derivatives']
    for item in derivatives:
        if "children" in item:
            children = item["children"]
            for child in children:
                if "children" in child:
                    sub_child = child['children']
                    for sub_urn in sub_child:
                        if "mime" in sub_urn and sub_urn["mime"] == "application/autodesk-svf":
                            svf_urns.append(sub_urn["urn"])
    if svf_urns:
        svf_urn = svf_urns[0]
        url = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/{new_urn}/manifest/{svf_urn}"
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        response = requests.get(url, headers=headers, stream=True)

        if response.status_code == 200:
            svf_content = response.content
            os.makedirs("svf_bundle/svf_file/bundle", exist_ok=True)

            with open("output.zip", "wb") as svf_file:
                svf_file.write(svf_content)

            with open("svf_bundle/svf_file/bundle/output.svf", "wb") as svf_file:
                svf_file.write(svf_content)

            archive = zipfile.ZipFile('output.zip', 'r')
            manifest_data = archive.read('manifest.json')
            manifest_json_data = json.loads(manifest_data)
            assets = manifest_json_data['assets']

            for asset in assets:
                uri_filename = asset["URI"]
                if uri_filename.startswith("../../"):
                    index = svf_urn.find("{3D}.svf")
                    modified_urn = svf_urn[:index] + uri_filename
                    last_slash_index = svf_urn.rfind('/')
                    modified_urn = svf_urn[:last_slash_index + 1] + uri_filename
                    asset_url = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/{new_urn}/manifest/{modified_urn}"
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                    }
                    asset_response = requests.get(asset_url, headers=headers, stream=True)
                    with open(f"svf_bundle/{uri_filename.split('/')[-1]}", 'wb') as svf_file:
                        svf_file.write(asset_response.content)
                elif uri_filename.startswith("embed:"):
                    pass
                else:
                    index = svf_urn.find("{3D}.svf")
                    modified_urn = svf_urn[:index] + uri_filename
                    last_slash_index = svf_urn.rfind('/')
                    modified_urn = svf_urn[:last_slash_index + 1] + uri_filename
                    asset_url = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/{new_urn}/manifest/{modified_urn}"
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                    }
                    asset_response = requests.get(asset_url, headers=headers, stream=True)
                    with open(f"svf_bundle/svf_file/bundle/{uri_filename}", 'wb') as svf_file:
                        svf_file.write(asset_response.content)

            print("SVF file downloaded successfully.")
        else:
            print("Failed to download SVF file.")
    else:
        print("No SVF URNs found in the manifest data.")
# Run the server
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)