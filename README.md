# Greengrass Accelerator Base

This repo contains a minimal deployment of Greengrass in AWS via the Cloud Development Kit (CDK), along with running Greengrass in a docker container.

It is used as scaffold for creating new accelerators, and will be updated as needed to refine constructs, versions, etc.

## Initial Use

Create an AWS profile that has the credentials needed to deploy the resources via CloudFormation.

Ensure CDK is installed and has been bootstrapped into the target account/region. 

```shell
npm install -g cdk
# Replace REGION with the specific region to bootstrap (e.g., us-east-1)
cdk bootstrap aws://unknown-account/REGION
```
The *cdk bootstrap* command wil use the default AWS CLI profile.

Also ensure that Docker is running and *Docker Compose* is installed.

Clone this repository locally and install modules:

```shell
git clone https://github.com/gadams999/greengrass-base-accelerator.git
cd greengrass-base-accelerator/cdk
npm install
```

Copy or rename `cdk/cdk.json.orig` to  `cdk.json`, then modify these attributes for your development use:

* `profile` - Name of AWS profile to use for permissions (must be changed from `REPLACE_WITH_PROFILE_NAME`)
* `context.stack_name` - CloudFormation stack name to use (must be changed from `REPLACE_WITH_STACK_NAME`)
* `context.region` - Region to deploy the stack in standard format such as *us-west-2* or *eu-west-1* (must be changed from `REPLACE_WITH_REGION_NAME`)

Initially, and after every change to CDK resources, build the components:

```shell
npm run build
```

And to deploy, run the deploy scripts that will create or update the CloudFormation stack, and also initially create the Greengrass files in the `gg_docker` directory (certificate, private key, and `config.json`). NOTE: These are only created from templates if the files do not exist.

```shell
npm run deploy
```

This will complete the deployment of the stack, and also run the `post_deploy_tasks.py` to:

* Read the certificate and private key from the AWS Systems Manager Parameter Store and place in the `gg_docker/certs` directory.
* Create a new Greengrass configuration file in `gg_docker/config/config.json` with the specifics for the stack. If the config file already exists, it will not be modified. This is useful for testing changes where the config file may had been modified.

Next, change to the `gg_docker/` directory, then build and start the docker container.


## Troubleshooting

* *Unable to resolve AWS account to use during Deployment* - Modify the `cdk/cdk.json` file and change the *profile* setting to an AWS profile (located in `~/.aws/config`). Save and then rerun the `npm run deploy` command.
* *Deployment failed: TES service role is not associated with this account.* - Verify there is a Greengrass service role for account associated with the target region. This must be completed on a per-region basis.