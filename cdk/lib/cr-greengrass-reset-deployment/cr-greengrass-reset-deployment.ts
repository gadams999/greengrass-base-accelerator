import * as cfn from "@aws-cdk/aws-cloudformation";
import * as lambda from "@aws-cdk/aws-lambda";
import * as iam from "@aws-cdk/aws-iam";
import * as cdk from "@aws-cdk/core";
import * as uuid from "uuid/v5";

import * as path from "path";

export interface CustomResourceGreengrassResetDeploymentProps {
  /**
   * Resource properties used to construct the custom resource and passed as dictionary
   * to the resource as part of the "ResourceProperties". Note that the properties below
   * will have an uppercase first character and the rest of the property kept intact.
   * For example, physicalId will be passed as PhysicalId
   */
  functionName: string;
  stackName: string;
  greengrassGroup: string;
  physicalId?: string;
}

export class CustomResourceGreengrassResetDeployment extends cdk.Construct {
  public readonly roleArn: string;
  // public resource: cfn.CustomResource;

  constructor(scope: cdk.Construct, id: string, props: CustomResourceGreengrassResetDeploymentProps) {
    super(scope, id);
    props.physicalId = props.functionName;

    new cfn.CustomResource(this, 'Resource', {
      provider: cfn.CustomResourceProvider.fromLambda(new lambda.SingletonFunction(this, 'Singleton', {
        functionName: props.functionName,
        uuid: uuid(props.functionName, uuid.DNS),
        code: lambda.Code.fromAsset(
          path.join(__dirname, "cr_greengrass_reset_deployment")
        ),
        handler: 'index.main',
        timeout: cdk.Duration.seconds(30),
        runtime: lambda.Runtime.PYTHON_3_8,
        initialPolicy: [
          new iam.PolicyStatement({
            actions: ['greengrass:*', 'iot:*'
            ],
            resources: ['*']
          })]
      })),
      properties: props
    });
  }
}

