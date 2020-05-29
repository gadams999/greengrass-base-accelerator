import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class CreateThing:
    """Create AWS IoT Thing"""
    def __init__(self, client, thing_name):
        self.client = client
        self.thing_name = thing_name

    def __enter__(self):
        logger.debug("enter context")
        response = self.client.create_thing(thingName=self.thing_name)
        thing_arn = response["thingArn"]
        return thing_arn

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logging.info("Thing successfully created")
            return True
        else:
            # Exception, so delete thing - no need to check for other principals as
            # failed on initial create
            logger.error("Exception raised, deleting thing")
            self.client.delete_thing(thingName=self.thing_name)
            logger.info("Thing successfully deleted")
            return False


class DeleteThing:
    """Delete AWS IoT Thing"""
    def __init__(self, client, thing_name):
        self.client = client
        self.thing_name = thing_name

    def __enter__(self):
        logger.debug("enter context")

        # Detach any other certificates or principals that may have been attached outside
        # of the CloudFormation process
        response = self.client.list_thing_principals(thingName=self.thing_name)
        for principal in response["principals"]:
            self.client.detach_thing_principal(
                thingName=self.thing_name, principal=principal
            )
        response = self.client.delete_thing(thingName=self.thing_name)
        logger.debug(f"DeleteThing response: {response}")
        return True

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.info("Thing successfully deleted")
            return True
        else:
            # Exception, could not delete thing
            logger.error(
                f"Unable to delete thing {self.thing_name}, error: {type} : {value}"
            )
            return False


class CreateCertKey:
    """Create AWS IoT certificate and private key"""
    def __init__(self, client):
        self.client = client
        self.values = {}

    def __enter__(self):
        logger.debug("enter context")
        response = self.client.create_keys_and_certificate(setAsActive=True)
        self.values = {
            "certificateArn": response["certificateArn"],
            "certificatePem": response["certificatePem"],
            "keyPem": response["keyPair"]["PrivateKey"],
        }
        return self.values

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.debug("Certifcate and private key successfully created")
            return True
        else:
            # Exception, so deactivate and delete thing
            logger.error("Exception raised, deleting certifcate")
            certificate_id = self.values["certificateArn"].split("/")[-1]
            self.client.update_certificate(
                certificateId=certificate_id, newStatus="INACTIVE"
            )
            self.client.delete_certificate(certificateId=certificate_id)
            return False


class DeleteCertKey:
    def __init__(self, client, cert_arn):
        self.client = client
        self.cert_arn = cert_arn

    def __enter__(self):
        logger.debug("enter context")
        certificate_id = self.cert_arn.split("/")[-1]
        response = self.client.update_certificate(
            certificateId=certificate_id, newStatus="INACTIVE"
        )
        logger.info(f"Deactivate certificate response: {response}")
        response = self.client.delete_certificate(certificateId=certificate_id)
        logger.info(f"Delete certifcate response: {response}")
        return True

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.info("Certificate successfully deleted")
            return True
        else:
            # Exception, so delete thing
            logger.error(
                f"Unabled to delete certificate {self.cert_arn}, error: {type} : {value}"
            )
            return False


class CreatePolicy:
    def __init__(self, client, policy_name, policy_document):
        self.client = client
        self.policy_name = policy_name
        self.policy_document = policy_document

    def __enter__(self):
        logger.debug("enter context")
        response = self.client.create_policy(
            policyName=self.policy_name, policyDocument=self.policy_document
        )
        policy = response["policyName"]
        return policy

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.info("Policy successfully created")
            return True
        else:
            # Exception
            logger.error("Exception raised, deleting policy")
            self.client.delete_policy(policyName=self.policy_name)
            logger.info("Policy successfully deleted")
            return False


class DeletePolicy:
    def __init__(self, client, policy_name):
        self.client = client
        self.policy_name = policy_name

    def __enter__(self):
        logger.debug("enter context")
        response = self.client.delete_policy(policyName=self.policy_name)
        print(f"Delete response: {response}")
        return True

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.info("Policy successfully deleted")
            return True
        else:
            # Exception, so delete thing
            logger.error(
                f"Unabled to delete policy {self.policy_name}, error: {type} : {value}"
            )
            return False


class AttachPrincipalPolicy:
    def __init__(self, client, principal, policy_name):
        self.client = client
        self.policy_name = policy_name
        self.principal = principal

    def __enter__(self):
        logger.debug("enter context")
        try:
            self.client.attach_principal_policy(
                policyName=self.policy_name, principal=self.principal
            )
            logger.info(f"Principal {self.principal} successfully attached to policy: {self.policy_name}")
            return True
        except ClientError as e:
            logger.error(
                f"Failed to attach {self.policy_name} to {self.principal}, error: {e}"
            )
            return False

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.info("Principal successfully attached to policy")
            return True
        else:
            # Exception, so delete thing
            logger.error("Exception raised, detaching principal from policy")
            self.client.detach_policy(
                policyName=self.policy_name, principal=self.principal
            )
            logger.info("Policy successfully detached from principal")
            return False


class DetachPrincipalPolicy:
    """Detach any policies from the principal"""

    def __init__(self, client, principal):
        self.client = client
        self.principal = principal

    def __enter__(self):
        logger.debug("enter context")
        response = self.client.list_attached_policies(target=self.principal)
        for policy in response["policies"]:
            self.client.detach_policy(
                policyName=policy["policyName"], target=self.principal
            )
            logger.info(
                f"Successfully detached policy: {policy['policyName']} from principal: {self.principal}"
            )
        return True

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.debug("Policy successfully detached from principal")
            return True
        else:
            # Exception, so delete thing
            logger.error(
                f"Unabled to detach all policies from {self.principal}, error: {type} : {value}"
            )
            return False


class AttachThingPrincipal:
    def __init__(self, client, thing_name, principal):
        self.client = client
        self.thing_name = thing_name
        self.principal = principal

    def __enter__(self):
        logger.debug("enter context")
        try:
            self.client.attach_thing_principal(
                thingName=self.thing_name, principal=self.principal
            )
            logger.info(f"Thing {self.thing_name} successfully attached to principal: {self.principal}")
            return True
        except ClientError as e:
            logger.error(
                f"Failed to attach {self.thing_name} to {self.principal}, error: {e}"
            )
            return False

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.info("Thing successfully attached to principal")
            return True
        else:
            # Exception, so undo
            logger.error("Exception raised, detaching thing from principal")
            self.client.detach_thing_principal(
                thingName=self.thing_name, principal=self.principal
            )
            logger.error("Thing successfully detached from principal")
            return False


class DetachThingPrincipal:
    """Detach any principals from the thing"""

    def __init__(self, client, thing_name):
        self.client = client
        self.thing_name = thing_name

    def __enter__(self):
        logger.debug("enter context")
        response = self.client.list_thing_principals(thingName=self.thing_name)
        for principal in response["principals"]:
            self.client.detach_thing_principal(
                thingName=self.thing_name, principal=principal
            )
            logger.info(f"Successfully detached  thing: {self.thing_name} from principal: {principal}")
        return True

    def __exit__(self, type, value, tb):
        logger.debug("exit context")
        if tb is None:
            # No exception, so just exit
            logger.debug("Thing successfully detached from principal")
            return True
        else:
            # Exception, so undo
            logger.error(
                f"Unabled to detach principals from {self.thing_name}, error: {type} : {value}"
            )
            return False
