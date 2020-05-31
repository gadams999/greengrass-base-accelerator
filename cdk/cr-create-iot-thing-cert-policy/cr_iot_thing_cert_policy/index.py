"""
Helper Custom Resource to create AWS IoT thing, certificate and IoT policy
"""

import json
import os
import logging
import time
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from iot.cm import (
    CreateThing,
    DeleteThing,
    CreateCertKey,
    DeleteCertKey,
    CreatePolicy,
    DeletePolicy,
    AttachPrincipalPolicy,
    DetachPrincipalPolicy,
    AttachThingPrincipal,
    DetachThingPrincipal,
)


__copyright__ = (
    "Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved."
)
__license__ = "MIT-0"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def create_iot_thing_certificate_policy(thing_name: str, policy_document: str):
    """Create IoT thing, AWS IoT generated certificate and private key,
       IoT policy for thing, then associate all.

       :param thing_name: name used for IoT Thing
       :param policy_document: JSON string of IoT policy actions
    """

    config = Config(retries=dict(max_attempts=5))
    iot_client = boto3.client("iot", config=config)
    policy_name = thing_name + "-cfn_created"
    response = {}

    # Single-shot create all resources
    with CreateThing(iot_client, thing_name) as thing:
        response["thingArn"] = thing
        with CreateCertKey(iot_client) as cert_key:
            # Adds certificateArn, certificatePem, and keyPem to response
            response.update(cert_key)
            with CreatePolicy(iot_client, policy_name, policy_document):
                response["policyName"] = policy_name
                with AttachPrincipalPolicy(
                    iot_client, response["certificateArn"], policy_name
                ):
                    with AttachThingPrincipal(
                        iot_client, thing_name, response["certificateArn"]
                    ):
                        # Completes the creation steps
                        pass

    # Describe the general ATS endpoint
    while True:
        try:
            r = iot_client.describe_endpoint(endpointType="iot:Data-ATS")
            response["endpointDataAts"] = r["endpointAddress"]
            break
        except ClientError as e:
            logger.warning(
                f"Error calling iot.describe_endpoint() to obtain iot:Data-ATS endpoint for thing {thing_name}, error: {e}"
            )
            time.sleep(2)
            continue

    return response


def delete_iot_thing_certificate_policy(
    thing_name: str, certificate_arn: str, policy_name: str
):
    """Delete IoT thing, AWS IoT generated certificate and private key,
       and IoT policy for thing. Only the referred resources are deleted, but
       any other associations to the thing or certifcate are also removed

       :param thing_name: Thing to delete
       :param certificate_arn: Certificate to deactivate and delete
       :param policy_name: IoT policy to detach and delete
    """

    config = Config(retries=dict(max_attempts=5))
    iot_client = boto3.client("iot", config=config)

    # Single-shot detach and delete all resources
    try:
        with DetachThingPrincipal(iot_client, thing_name):
            logging.info(f"All principals detached from {thing_name}")
            with DetachPrincipalPolicy(iot_client, certificate_arn):
                logging.info(
                    f"All policies detached from certificate arn: {certificate_arn}"
                )
                with DeletePolicy(iot_client, policy_name):
                    logging.info(f"Policy: {policy_name} deleted")
                    with DeleteCertKey(iot_client, certificate_arn):
                        logging.info(f"Certificate arn: {certificate_arn} deleted")
                        with DeleteThing(iot_client, thing_name) as thing:
                            logging.info(f"Thing: {thing} deleted")
        return True
    except:
        # Exception on the delete process, log and return cfnresponse failed
        return False


def put_parameter(name, value, type="String"):
    """Place value into Parameter store as string using name"""
    config = Config(retries=dict(max_attempts=5))
    client = boto3.client("ssm", config=config)
    try:
        client.put_parameter(Name=name, Value=value, Type=type, Overwrite=True)
    except ClientError as e:
        logger.error(
            f"Error creating or updating parameter: {name} with value: {value}, error: {e}"
        )
        return False


def get_parameter(name):
    """Return value from Parameter Store"""
    config = Config(retries=dict(max_attempts=5))
    client = boto3.client("ssm", config=config)
    try:
        return client.get_parameter(Name=name)["Parameter"]["Value"]
    except ClientError as e:
        logger.error(f"Error getting parameter: {name}, error: {e}")
        return False


def delete_parameter(name):
    """Delete the parameter from the Parameter Store"""
    config = Config(retries=dict(max_attempts=5))
    client = boto3.client("ssm", config=config)
    try:
        client.delete_parameter(Name=name)
    except ClientError as e:
        logger.error(f"Error deleting parameter: {name}, error: {e}")
        return False


def delete_parameters(filter):
    """Deletes all parameters that match the filter from the Parameter Store"""

    config = Config(retries=dict(max_attempts=5))
    client = boto3.client("ssm", config=config)
    # Return all parameters that match the filter
    for key in paginate(
        client.describe_parameters,
        ParameterFilters=[{"Key": "Path", "Values": [filter,]},],
    ):
        try:
            client.delete_parameter(Name=key["Name"])
            logger.info(f"For filter: {filter}, deleted key {key['Name']}")
        except ClientError as e:
            logger.error(f"Error deleting parameter: {key['Name']} , error: {e}")


def paginate(method, **kwargs):
    """Paginate as needed for boto3 calls"""
    client = method.__self__
    paginator = client.get_paginator(method.__name__)
    for page in paginator.paginate(**kwargs).result_key_iters():
        for result in page:
            yield result


def main(event, context):
    import logging as log
    import cfnresponse

    # Ability to set event context to different logging level than called functions
    log.getLogger().setLevel(log.INFO)

    # NOTE: All ResourceProperties passed will uppercase the first letter
    #       of the property and leave the rest of the case intact.

    physical_id = event["ResourceProperties"]["PhysicalId"]
    stack_name = str(event["StackId"].split(":")[-1:][0]).split("/")[1]
    cfn_response = cfnresponse.SUCCESS

    try:
        log.info("Input event: %s", event)

        # Check if this is a Create and we're failing Creates
        if event["RequestType"] == "Create" and event["ResourceProperties"].get(
            "FailCreate", False
        ):
            raise RuntimeError("Create failure requested, logging")
        elif event["RequestType"] == "Create":
            # Operations to perform during Create, then return response_data
            response = create_iot_thing_certificate_policy(
                thing_name=event["ResourceProperties"]["IotThingName"],
                policy_document=event["ResourceProperties"]["IotPolicy"],
            )
            if response == False:
                raise Exception("Failure to create thing/cert/policy")

            # Resources created, put values into parameter store for others to access
            put_parameter(
                name=f"/{stack_name}/certificate_arn", value=response["certificateArn"]
            )
            put_parameter(
                name=f"/{stack_name}/policy_name", value=response["policyName"]
            )
            # Store certificate and private key in parameter store
            put_parameter(
                name=f"/{stack_name}/certificate_pem", value=response["certificatePem"]
            )
            put_parameter(
                name=f"/{stack_name}/privatekey_pem",
                value=response["privateKeyPem"],
                type="SecureString",
            )
            # Thing Arn and endpoints (used to craft config.json)
            put_parameter(name=f"/{stack_name}/thing_arn", value=response["thingArn"])
            put_parameter(
                name=f"/{stack_name}/endpoint_data_ats",
                value=response["endpointDataAts"],
            )
            # Data to be returned for use by the rest of the calling CloudFormation stack
            response_data = {
                "thingArn": response["thingArn"],
                "certificateArn": response["certificateArn"],
            }
        elif event["RequestType"] == "Update":
            # Operations to perform during Update, then return NULL for response data
            response_data = {}
        else:
            # DELETE RequestType
            # Delete all resources
            if delete_iot_thing_certificate_policy(
                thing_name=event["ResourceProperties"]["IotThingName"],
                certificate_arn=get_parameter(f"/{stack_name}/certificate_arn"),
                policy_name=get_parameter(f"/{stack_name}/policy_name"),
            ):
                logging.info("All resources deleted")
                # On successful resource delete, clear out all parameters for the stack
                delete_parameters(f"/{stack_name}")
                logging.info(f"All {stack_name} parameters deleted")
            else:
                # there was an error deleting, alert
                cfn_response = cfnresponse.FAILED
            response_data = {}
        cfnresponse.send(event, context, cfn_response, response_data, physical_id)

    except Exception as e:
        log.exception(e)
        # cfnresponse error message is always "see CloudWatch"
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, physical_id)
