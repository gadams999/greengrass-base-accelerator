"""
Post-deploy script to create resources and automatically create a deployment step 
for the Greengrass Group
"""


import json
import sys
import logging
from pathlib import Path
from urllib import request
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Template is only for Greengrass 1.10.0 and newer
config_json_template = {
    "coreThing": {
        "caPath": "root.ca.pem",
        "certPath": "certificate.pem",
        "keyPath": "private.key",
        "thingArn": None,
        "iotHost": None,
        "ggHost": "greengrass-ats.iot.region.amazonaws.com",
        "keepAlive": 600,
    },
    "runtime": {
        "maxWorkItemCount": 1024,
        "cgroup": {"useSystemd": "yes"},
        "allowFunctionsToRunAsRoot": "yes",
    },
    "managedRespawn": False,
    "crypto": {
        "principals": {
            "SecretsManager": {
                "privateKeyPath": "file:///greengrass/certs/private.key"
            },
            "IoTCertificate": {
                "privateKeyPath": "file:///greengrass/certs/private.key",
                "certificatePath": "file:///greengrass/certs/certificate.pem",
            },
        },
        "caPath": "file:///greengrass/certs/root.ca.pem",
    },
}


def read_manifest():
    """Read the CDK manifest file to get the stackname

        As of cdk 1.13.1, the stackname can be found in the manifest file
        as an artifact object with a type of aws:cloudformation:stack    
    """

    manifest_file = Path("cdk.out/manifest.json")
    if manifest_file.is_file():
        with open(manifest_file) as f:
            manifest = f.read()
    else:
        print("manifest.json not found in cdk.out directory.")
        sys.exit(1)

    try:
        manifest = json.loads(manifest)
    except ValueError as e:
        print(f"Invalid format of {manifest_file}, error: {e}")
        sys.exit(1)
    # Only return the first artifact
    for i in manifest["artifacts"]:
        if manifest["artifacts"][i]["type"] == "aws:cloudformation:stack":
            return i


def get_parameter(client, name, type="String"):
    """Return value from Parameter Store"""

    try:
        if type == "SecureString":
            return client.get_parameter(Name=name, WithDecryption=True)["Parameter"][
                "Value"
            ]
        else:
            return client.get_parameter(Name=name)["Parameter"]["Value"]
    except ClientError as e:
        logger.error(f"Error getting parameter: {name}, error: {e}")
        return False


def find_group_id(group_name, client):
    """Return Greengrass group id"""
    result = ""

    response = client.list_groups()
    for group in response["Groups"]:
        if group_name == group["Name"]:
            result = group["Id"]
            break
    return result


def deploy_group(greengrass_group_name, client):
    """Deploy group to core"""

    group_id = find_group_id(greengrass_group_name, client)
    logger.info("Group id to deploy: %s" % group_id)
    if group_id:
        group_version = client.list_group_versions(GroupId=group_id)["Versions"][0][
            "Version"
        ]
        client.create_deployment(
            DeploymentType="NewDeployment",
            GroupId=group_id,
            GroupVersionId=group_version,
        )
        logger.info("Initiated Greengrass deployment to the group")
    else:
        logger.info("No group Id %s found, cannot deploy" % greengrass_group_name)
    return


if __name__ == "__main__":
    # Read config file
    print("Reading deployed CDK manifest file contents")
    stackname = read_manifest()

    # Read profile name and region from cdk.json
    with open("cdk.json") as f:
        data = json.load(f)
        profile = data["profile"]
        region = data["context"]["region"]

    # Get values from Parameter Store to create files and config.json
    session = boto3.Session(profile_name=profile, region_name=region)
    ssm = session.client("ssm")
    certificate_pem = get_parameter(ssm, f"/{stackname}/certificate_pem")
    privatekey_pem = get_parameter(
        ssm, f"/{stackname}/privatekey_pem", type="SecureString"
    )
    thing_arn = get_parameter(ssm, f"/{stackname}/thing_arn")
    endpoint = get_parameter(ssm, f"/{stackname}/endpoint_data_ats")

    # Create the credentials files and download the Amazon root CA1 file
    with open(Path("../gg_docker/certs/certificate.pem"), "w") as f:
        # Thing's certificate
        f.write(certificate_pem)
    with open(Path("../gg_docker/certs/private.key"), "w") as f:
        # Thing's private key
        f.write(privatekey_pem)
    # Root CA file
    url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
    request.urlretrieve(url, Path("../gg_docker/certs/root.ca.pem"))

    # Create the config.json file from template if it doesn't already exist, then update specific attributes
    if not Path("../gg_docker/config/config.json").is_file():
        print("Creating NEW config.json file")
        config_file = config_json_template
        config_file["coreThing"]["thingArn"] = "arn:aws:iot:{}:{}:thing/{}".format(
            thing_arn.split(":")[3], thing_arn.split(":")[4], thing_arn.split("/")[-1]
        )
        config_file["coreThing"]["iotHost"] = endpoint
        config_file["coreThing"][
            "ggHost"
        ] = "greengrass-ats.iot.{}.amazonaws.com".format(thing_arn.split(":")[3])
        with open(Path("../gg_docker/config/config.json"), "w") as f:
            # Specific unique configuration file
            f.write(json.dumps(config_file, indent=2))
    else:
        print("config.json file already exists, NOT modified")

    # Perform a Greengrass deployment so that the next start of greengrassd will start the download
    greengrass = session.client("greengrass")
    deploy_group(stackname.replace("-", "_"), greengrass)
