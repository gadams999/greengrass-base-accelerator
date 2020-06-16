import json
import sys
import argparse
import logging
from pathlib import Path
from urllib import request
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.WARNING)

parser = argparse.ArgumentParser()
parser.add_argument(
    "-p",
    "--profile",
    action="store",
    required=True,
    dest="profile",
    help="Your AWS CLI profile name",
)

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


if __name__ == "__main__":
    # Confirm profile given as parameters
    args = parser.parse_args()
    print(args.profile)

    # Read config file
    print("Reading deployed CDK manifest file contents")
    stackname = read_manifest()

    # Get values from Parameter Store to create files and config.json
    session = boto3.Session(profile_name=args.profile)
    ssm = session.client("ssm")
    certificate_pem = get_parameter(ssm, f"/{stackname}/certificate_pem")
    privatekey_pem = get_parameter(
        ssm, f"/{stackname}/privatekey_pem", type="SecureString"
    )
    thing_arn = get_parameter(ssm, f"/{stackname}/thing_arn")
    endpoint = get_parameter(ssm, f"/{stackname}/endpoint_data_ats")

    # Create the credentials files, config.json, and download the Amazon root CA1 file
    with open(Path("../gg_docker/certs/certificate.pem"), "w") as f:
        # Thing's certificate
        f.write(certificate_pem)
    with open(Path("../gg_docker/certs/private.key"), "w") as f:
        # Thing's private key
        f.write(privatekey_pem)
    # Root CA file
    url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
    request.urlretrieve(url, Path("../gg_docker/certs/root.ca.pem"))

    # Create the config.json file from template, then update specific attributes
    config_file = config_json_template
    config_file["coreThing"]["thingArn"] = "arn:aws:iot:{}:{}:thing/{}".format(
        thing_arn.split(":")[3], thing_arn.split(":")[4], thing_arn.split("/")[-1]
    )
    config_file["coreThing"]["iotHost"] = endpoint
    config_file["coreThing"]["ggHost"] = "greengrass-ats.iot.{}.amazonaws.com".format(
        thing_arn.split(":")[3]
    )
    with open(Path("../gg_docker/config/config.json"), "w") as f:
        # Specific unique configuration file
        f.write(json.dumps(config_file, indent=2))

    # Addition accelerator specific steps go here
