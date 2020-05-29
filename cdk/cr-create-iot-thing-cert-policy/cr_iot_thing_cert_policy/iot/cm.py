import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class CreateThing:
    def __init__(self, client, thing_name):
        print("in init")
        self.client = client
        self.thing_name = thing_name

    def __enter__(self):
        print("in enter")
        response = self.client.create_thing(thingName=self.thing_name)
        thing_arn = response["thingArn"]
        return thing_arn

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, thing created")
            return True
        else:
            # Exception, so delete thing - no need to check for other principals as
            # failed on initial create
            print("got an exception, delete thing")
            self.client.delete_thing(thingName=self.thing_name)
            print("thing deleted")
            return False


class DeleteThing:
    def __init__(self, client, thing_name):
        print("in init")
        self.client = client
        self.thing_name = thing_name

    def __enter__(self):
        print("in enter")

        # Detach any other certificates or principals that may have been attached outside
        # of the CloudFormation process
        response = self.client.list_thing_principals(thingName=self.thing_name)
        for principal in response["principals"]:
            self.client.detach_thing_principal(
                thingName=self.thing_name, principal=principal
            )
        response = self.client.delete_thing(thingName=self.thing_name)
        print(f"Delete response: {response}")
        return True

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, thing DELETED")
            return True
        else:
            # Exception, so delete thing
            print("got an exception, log error")
            logger.error(
                f"Unabled to delete thing {self.thing_name}, error: {type} : {value}"
            )
            return False


class CreateCertKey:
    def __init__(self, client):
        print("in init")
        self.client = client
        self.values = {}

    def __enter__(self):
        print("in enter")
        response = self.client.create_keys_and_certificate(setAsActive=True)
        self.values = {
            "certificateArn": response["certificateArn"],
            "certificatePem": response["certificatePem"],
            "keyPem": response["keyPair"]["PrivateKey"],
        }
        return self.values

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, cert and key created")
            return True
        else:
            # Exception, so deactivate and delete thing
            print("got an exception, delete certifcate and key")
            certificate_id = self.values["certificateArn"].split("/")[-1]
            self.client.update_certificate(
                certificateId=certificate_id, newStatus="INACTIVE"
            )
            self.client.delete_certificate(certificateId=certificate_id)
            return False


class DeleteCertKey:
    def __init__(self, client, cert_arn):
        print("in init")
        self.client = client
        self.cert_arn = cert_arn

    def __enter__(self):
        print("in enter")
        certificate_id = self.cert_arn.split("/")[-1]
        response = self.client.update_certificate(
            certificateId=certificate_id, newStatus="INACTIVE"
        )
        print(f"deactivate cert response: {response}")
        response = self.client.delete_certificate(certificateId=certificate_id)
        print(f"Delete cert response: {response}")
        return True

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, certificate DELETED")
            return True
        else:
            # Exception, so delete thing
            print("got an exception, log error")
            logger.error(
                f"Unabled to delete certificate {self.cert_arn}, error: {type} : {value}"
            )
            return False


class CreatePolicy:
    def __init__(self, client, policy_name, policy_document):
        print("in init")
        self.client = client
        self.policy_name = policy_name
        self.policy_document = policy_document

    def __enter__(self):
        print("in enter")
        response = self.client.create_policy(
            policyName=self.policy_name, policyDocument=self.policy_document
        )
        policy = response["policyName"]
        return policy

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, policy created")
            return True
        else:
            # Exception, so delete thing
            print("got an exception, delete policy")
            self.client.delete_policy(policyName=self.policy_name)
            print("policy deleted")
            return False


class DeletePolicy:
    def __init__(self, client, policy_name):
        print("in init")
        self.client = client
        self.policy_name = policy_name

    def __enter__(self):
        print("in enter")
        response = self.client.delete_policy(policyName=self.policy_name)
        print(f"Delete response: {response}")
        return True

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, policy DELETED")
            return True
        else:
            # Exception, so delete thing
            print("got an exception, log error")
            logger.error(
                f"Unabled to delete policy {self.policy_name}, error: {type} : {value}"
            )
            return False


class AttachPrincipalPolicy:
    def __init__(self, client, principal, policy_name):
        print("in init")
        self.client = client
        self.policy_name = policy_name
        self.principal = principal

    def __enter__(self):
        print("in enter")
        try:
            self.client.attach_principal_policy(
                policyName=self.policy_name, principal=self.principal
            )
            return True
        except ClientError as e:
            logger.error(
                f"Failed to attach {self.policy_name} to {self.principal}, error: {e}"
            )
            return False

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, principal attached to policy")
            return True
        else:
            # Exception, so delete thing
            print("got an exception, detach principal from policy")
            self.client.detach_policy(
                policyName=self.policy_name, principal=self.principal
            )
            print("policy detached from principal")
            return False


class DetachPrincipalPolicy:
    """Detach any policies from the principal"""

    def __init__(self, client, principal):
        print("in init")
        self.client = client
        self.principal = principal

    def __enter__(self):
        print("in enter")
        response = self.client.list_attached_policies(target=self.principal)
        for policy in response["policies"]:
            self.client.detach_policy(
                policyName=policy["policyName"], target=self.principal
            )
            print(
                f"detached policy: {policy['policyName']} from principal: {self.principal}"
            )
        return True

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, policy detached from principal")
            return True
        else:
            # Exception, so delete thing
            print("got an exception, log error")
            logger.error(
                f"Unabled to detach policies from {self.principal}, error: {type} : {value}"
            )
            return False


class AttachThingPrincipal:
    def __init__(self, client, thing_name, principal):
        print("in init")
        self.client = client
        self.thing_name = thing_name
        self.principal = principal

    def __enter__(self):
        print("in enter")
        try:
            self.client.attach_thing_principal(
                thingName=self.thing_name, principal=self.principal
            )
            return True
        except ClientError as e:
            logger.error(
                f"Failed to attach {self.thing_name} to {self.principal}, error: {e}"
            )
            return False

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, principal attached to thing")
            return True
        else:
            # Exception, so undo
            print("got an exception, detach principal from thing")
            self.client.detach_thing_principal(
                thingName=self.thing_name, principal=self.principal
            )
            print("thing detached from principal")
            return False


class DetachThingPrincipal:
    """Detach any principals from the thing"""

    def __init__(self, client, thing_name):
        print("in init")
        self.client = client
        self.thing_name = thing_name

    def __enter__(self):
        print("in enter")
        response = self.client.list_thing_principals(thingName=self.thing_name)
        for principal in response["principals"]:
            self.client.detach_thing_principal(
                thingName=self.thing_name, principal=principal
            )
            print(f"detached principal: {principal} from thing: {self.thing_name}")
        return True

    def __exit__(self, type, value, tb):
        print("in exit")
        if tb is None:
            # No exception, so just exit
            print("no error, thing detached from principal")
            return True
        else:
            # Exception, so undo
            print("got an exception, log error")
            logger.error(
                f"Unabled to detach principals from {self.thing_name}, error: {type} : {value}"
            )
            return False
