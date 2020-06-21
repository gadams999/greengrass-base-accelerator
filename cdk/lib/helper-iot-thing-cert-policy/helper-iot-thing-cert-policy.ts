import * as cfn from "@aws-cdk/aws-cloudformation";
import * as lambda from "@aws-cdk/aws-lambda";
import * as iam from "@aws-cdk/aws-iam";
import * as cdk from "@aws-cdk/core";
import * as uuid from "uuid/v5";

import * as path from "path";

export interface HelperIoTThingCertPolicyProps {
    /**
     * Resource properties used to construct the custom resource and passed as dictionary
     * to the resource as part of the "ResourceProperties". Note that the properties below
     * will have an uppercase first character and the rest of the property kept intact.
     * For example, physicalId will be passed as PhysicalId
     */
    functionName: string;
    iotThingName: string;
    iotPolicy: string;
    // Set as prop to pass along to Lambda, set as functionName
    physicalId?: string;
}

export class HelperIoTThingCertPolicy extends cdk.Construct {
    /**
     * Creates an IoT Thing, certificate with private key, AWS IoT policy, and returns the
     * created resources and CloudFormation outputs.
     *
     * @remarks
     * this construct creates all components needed for an IoT Core
     *
     * @param functionName - Name for the Lambda helper function
     * @param iotThingName - Base name for core thing name - if not provided the name is derived from the stack name
     * @param iotPolicy - JSON string IoT policy for Thing - policy name derived from Thing name
     * @returns String values for `certificateArn` and `thingArn` to be referenced by other CloudFormation outputs.
     */
    public readonly certificateArn: string;
    public readonly thingArn: string;

    constructor(
        scope: cdk.Construct,
        id: string,
        props: HelperIoTThingCertPolicyProps
    ) {
        super(scope, id);
        props.physicalId = props.functionName;
        const resource = new cfn.CustomResource(this, "Resource", {
            provider: cfn.CustomResourceProvider.fromLambda(
                new lambda.SingletonFunction(this, "Singleton", {
                    functionName: props.functionName,
                    uuid: uuid(props.functionName, uuid.DNS),
                    code: lambda.Code.fromAsset(
                        path.join(__dirname, "helper_iot_thing_cert_policy")
                    ),
                    handler: "index.main",
                    timeout: cdk.Duration.seconds(30),
                    runtime: lambda.Runtime.PYTHON_3_8,
                    // Policy for Lambda to action on IoT resources - TODO - scope down to actions taken by Lambda
                    initialPolicy: [
                        new iam.PolicyStatement({
                            actions: ["iot:*"],
                            resources: ["*"],
                        }),
                        new iam.PolicyStatement({
                            actions: [
                                "ssm:DescribeParameters",
                                "ssm:DeleteParameter",
                                "ssm:GetParameter",
                                "ssm:PutParameter",
                            ],
                            resources: ["*"],
                        }),
                    ],
                })
            ),
            properties: props,
        });
        // Set resource return values for use by other CDK constructs
        this.thingArn = resource.getAttString("thingArn");
        this.certificateArn = resource.getAttString("certificateArn");
    }
}
