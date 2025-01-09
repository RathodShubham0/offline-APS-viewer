import boto3
import requests
import os
import json
import time
import base64
import zipfile

# Create one downloads folder
# WORKFLOW:
# It downloads latest file from S3 bucket and uploads to OSS, to translate
# Once translate is complete, we store manifest.json output into .zip
# after .zip file extraction search of 'output.svf' file inside 'svf_bundle' folder

#boto3.setup_default_session(profile_name='cctech', region_name='ap-south-1')
s3 = boto3.client('s3', region_name='ap-south-1')

# comment added
bucket = ''
client_id = ''
client_secret = ''
oss_bucket_name = ''

def two_legged_access_token():
    url = "https://developer.api.autodesk.com/authentication/v1/authenticate"
    payload = f'client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials&scope=data%3Awrite%20data%3Aread%20bucket%3Acreate%20bucket%3Adelete'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    access_token = response.json()['access_token']
    return access_token
def getAuthToken():
    """ Get the auth token """
    apiUrl = "https://77fvkau4nd.execute-api.ap-south-1.amazonaws.com/test/auth"
    data = {}
    token = 0
    try:
        print("Sending request to get the access token")
        res = requests.post(apiUrl, json=data)
        # Parse the JSON response if the request was successful
        if res.status_code != 200:
            print(f"Request failed with status code: {res.status_code}")
            return 0
        jsonResponse = res.json()
        if jsonResponse:
            if jsonResponse['body']:
                # Extract the access_token value from the body
                body = json.loads(jsonResponse['body'])
                token = body.get('access_token', 0)
                print("Fetched the token successfully")
        if not token: print("Access token not found, Unable to publish the final model.")
    except Exception as e:
        print(f"Error while processing the url : {str(e)}")
    return token

def get_most_recent_file(bucket_name):
    response = s3.list_objects_v2(Bucket=bucket_name)

    if 'Contents' in response:
        objects = response['Contents']
        most_recent_file = max(objects, key=lambda x: x['LastModified'])
        return most_recent_file['Key']
    else:
        return None


def download_svf_endpoint():
    most_recent_file = get_most_recent_file(bucket)
    cur_path = os.getcwd()
    # file = 'updated Quad-Lock_BIM_Revit_IMPERIAL_2024.0001.rvt'
    file_path = os.path.join(cur_path, 'downloads', most_recent_file)
    s3.download_file(Bucket=bucket, Key=most_recent_file, Filename=file_path)
    print("File from S3 downloaded successfully")
    return most_recent_file


def get_signed_url_of_assembly_file(access_token):
    file = download_svf_endpoint()
    url = f'https://developer.api.autodesk.com/oss/v2/buckets/intech_lattice_demo/objects/{file}/signeds3upload?minutesExpiration=15'

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "ossbucketKey": oss_bucket_name,
        "ossSourceFileObjectKey": file,
        "access": "full",
        "policyKey": "transient"
    }

    response = requests.get(url, headers=headers, json=data)

    if response.status_code == 200:
        print("Received signed url")
        return (response.json(), file)
    else:
        return ("Error:", response.status_code)


def assembly_file_upload(access_token):
    response, file = get_signed_url_of_assembly_file(access_token)
    signed_upload_url = response['urls'][0]
    upload_key = response['uploadKey']
    path_to_file = f'downloads/{file}'

    with open(path_to_file, 'rb') as f:
        response = requests.put(signed_upload_url, data=f)

    if response.status_code == 200:
        print("Assembly file uploaded")
        return upload_key, file
    else:
        return ("Error:", response.status_code)


def final_file_upload(access_token):
    upload_key, file = assembly_file_upload(access_token)
    print("final file upload on OSS begin")
    url = f'https://developer.api.autodesk.com/oss/v2/buckets/intech_lattice_demo/objects/{file}/signeds3upload'

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "ossbucketKey": "intech_lattice_demo",
        "ossSourceFileObjectKey": file,
        "access": "full",
        "uploadKey": upload_key
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        # return("Response:", response.json()['objectId'])
        base64_urn = base64.b64encode(
            response.json()['objectId'].encode()).decode()
        print("Model transalation begin")

        model_translation(base64_urn, access_token, file)
    else:
        return ("Error:", response.status_code)


def model_translation(base64_urn, access_token, file):
    url = "https://developer.api.autodesk.com/modelderivative/v2/designdata/job"
    payload = json.dumps({
        "input": {
            "urn": base64_urn},
        "output": {
            "destination": {
                "region": "us"
            },
            "formats": [
                {
                    "type": "svf",
                    "views": ["2d","3d"]
                }
            ]
        }
    })
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'x-ads-force': 'true'}
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code == 200:
        print("Translation completed")
        new_urn = response.json()['urn']
        get_manifest(new_urn, access_token, file)

    # return new_urn


def get_manifest(new_urn, access_token, file):
    # new_urn = model_translation(access_token)
    base_url = "https://developer.api.autodesk.com/modelderivative/v2/designdata"
    endpoint = f"{base_url}/{new_urn}/manifest"

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        response = requests.get(endpoint, headers=headers)

        manifest_data = response.json()
        status = manifest_data['status']

        print("Status of manifest ", status)

        if status == "success":
            manifest_data = response.json()
            download_svf_file_url(manifest_data, new_urn, access_token, file)
            # return manifest_data, new_urn

        elif status == "failed":
            return "failed"

        elif status in ["pending", "inprogress"]:
            time.sleep(10)
            return get_manifest(new_urn, access_token, file)

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def download_svf_file_url(manifest_data, new_urn, access_token, file):

    # manifest_data,new_urn = get_manifest(access_token)
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
            # s3.put_object(Bucket=bucket, Key="downloaded_svf/output.svf", Body=svf_content)
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
                    gz_file_name = uri_filename
                    modified_urn = svf_urn.split("/")
                    last_slash_index = svf_urn.rfind('/')
                    modified_urn = svf_urn[:last_slash_index + 1]+uri_filename
                    asset_url = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/{new_urn}/manifest/{modified_urn}"
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                    }
                    asset_response = requests.get(
                        asset_url, headers=headers, stream=True)
                    with open(f"svf_bundle/{gz_file_name[-1]}", 'wb') as svf_file:
                        svf_file.write(asset_response.content)
                elif uri_filename.startswith("embed:"):
                    pass
                else:
                    index = svf_urn.find("{3D}.svf")
                    modified_urn = svf_urn[:index] + uri_filename
                    modified_urn = svf_urn.split("/")
                    last_slash_index = svf_urn.rfind('/')
                    modified_urn = svf_urn[:last_slash_index + 1]+uri_filename
                    asset_url = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/{new_urn}/manifest/{modified_urn}"
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                    }
                    asset_response = requests.get(
                        asset_url, headers=headers, stream=True)
                    with open(f"svf_bundle/svf_file/bundle/{uri_filename}", 'wb') as svf_file:
                        svf_file.write(asset_response.content)

            print("SVF file downloaded successfully.")
            remove_file_from_oss(
                'local-data-residency-demo', file, access_token)
        else:
            print("Failed to download SVF file.")
    else:
        print("No SVF urns found in the manifest data.")


def remove_file_from_oss(bucket_key, object_key, access_token):
    url = f"https://developer.api.autodesk.com/oss/v2/buckets/{bucket_key}/objects/{object_key}"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        print("File removed from OSS successfully.")
    else:
        print("Failed to remove file from OSS:", response.status_code)


def main():
    access_token = getAuthToken()
    final_file_upload(access_token)


if __name__ == "__main__":
    main()
