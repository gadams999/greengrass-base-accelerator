"""
Custom resource function to reset a Greengrass deployment prior to deleting Greengrass Group
"""

import json
import os
import logging
import time
import boto3
import cfnresponse
from botocore.exceptions import ClientError

__copyright__ = (
    "Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved."
)
__license__ = "MIT-0"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def find_group_id(group_name):
    """Return Greengrass group id"""
    result = ""
    greengrass_client = boto3.client("greengrass")

    response = greengrass_client.list_groups()
    for group in response["Groups"]:
        if group_name == group["Name"]:
            result = group["Id"]
            break
    return result


def deploy_group(greengrass_group_name):
    """Deploy group to core"""
    greengrass_client = boto3.client("greengrass")

    group_id = find_group_id(greengrass_group_name)
    logger.info("Group id to deploy: %s" % group_id)
    if group_id:
        group_version = greengrass_client.list_group_versions(GroupId=group_id)[
            "Versions"
        ][0]["Version"]
        greengrass_client.create_deployment(
            DeploymentType="NewDeployment",
            GroupId=group_id,
            GroupVersionId=group_version,
        )
        logger.info("Initiated Greengrass deployment to the group")
    else:
        logger.info("No group Id %s found, cannot deploy" % greengrass_group_name)
    return cfnresponse.SUCCESS


def reset_deployment(greengrass_group_name):
    """Force reset of the greengrass group"""
    greengrass_client = boto3.client("greengrass")

    group_id = find_group_id(greengrass_group_name)
    logger.info("Group id to reset deployment: %s" % group_id)
    if group_id:
        greengrass_client.reset_deployments(Force=True, GroupId=group_id)
        logger.info("Forced reset of Greengrass deployment")
    else:
        logger.error("No group Id %s found, reset not required" % greengrass_group_name)
    return cfnresponse.SUCCESS


def main(event, context):

    # greengrass_client = boto3.client("greengrass")

    # NOTE: All ResourceProperties passed will uppercase the first letter
    #       of the property and leave the rest of the case intact.

    physical_id = event["ResourceProperties"]["PhysicalId"]
    cfn_response = cfnresponse.SUCCESS

    try:
        logger.info("Input event: %s", event)

        # Check if this is a Create and we're failing Creates
        if event["RequestType"] == "Create" and event["ResourceProperties"].get(
            "FailCreate", False
        ):
            raise RuntimeError("Create failure requested, logging")
        elif event["RequestType"] == "Create":
            # No action needed on resource 
            logger.info("Creating called, no operations required")
            response_data = {}
        elif event["RequestType"] == "Update":
            # A stack update may force Greengrass to delete the current group. In this case
            # a forced reset is needed to allow that to happen. Call out in docs that
            # this will require a manual deployment to take place.
            logger.info("Update called, perform a deployment reset")
            cfn_response = reset_deployment(
                event["ResourceProperties"]["GreengrassGroup"]
            )
            response_data = {}
        else:
            # Delete request
            # Reset deployment for Greengrass
            logger.info(
                "Delete called, will attempt to reset Deployment on %s"
                % event["ResourceProperties"]["GreengrassGroup"]
            )
            cfn_response = reset_deployment(
                event["ResourceProperties"]["GreengrassGroup"]
            )
            response_data = {}
        cfnresponse.send(event, context, cfn_response, response_data, physical_id)

    except Exception as e:
        logger.exception(e)
        # cfnresponse error message is always "see CloudWatch"
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, physical_id)
