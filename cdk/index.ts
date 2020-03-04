import cdk = require('@aws-cdk/core');
import greengrass = require('@aws-cdk/aws-greengrass');
import { CustomResourceIoTThingCertPolicy } from './cr-create-iot-thing-cert-policy/cr-iot-thing-cert-policy';
import { CustomResourceGreengrassServiceRole } from './cr-greengrass-service-role/cr-greengrass-service-role';
import { CustomResourceGreengrassResetDeployment } from './cr-greengrass-reset-deployment/cr-greengrass-reset-deployment';
import { GreengrassLambdaBASE } from './lambda-gg-base/lambda-gg-base';

/**
 * A stack that sets up a Greengrass Group and all support resources
 */
class GreengrassBaseStack extends cdk.Stack {
    constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // Create AWS IoT Thing/Certificate/Policy as basis for Greengrass Core
        const crIoTResource = new CustomResourceIoTThingCertPolicy(this, 'CreateThingCertPolicyCustomResource', {
            functionName: id + '-CreateThingCertPolicyFunction',
            stackName: id,
        });
        new cdk.CfnOutput(this, 'CertificatePEM', {
            description: 'Certificate of Greengrass Core thing',
            value: crIoTResource.certificatePem
        });
        new cdk.CfnOutput(this, 'PrivateKeyPEM', {
            description: 'Private Key of Greengrass Core thing',
            value: crIoTResource.privateKeyPem
        });
        new cdk.CfnOutput(this, 'ThingArn', {
            description: 'Arn for IoT thing',
            value: crIoTResource.thingArn
        });
        new cdk.CfnOutput(this, 'EndpointDataAts', {
            description: 'IoT data endpoint',
            value: crIoTResource.endpointDataAts
        });

        // Create Greengrass Service role with permissions the Core's resources should have
        const ggServiceRole = new CustomResourceGreengrassServiceRole(this, "GreengrassRoleCustomResource", {
            functionName: id + '-GreengrassRoleFunction',
            stackName: id,
            rolePolicy: {
                "Version": "2012-10-17",
                "Statement": [
                    // Allow All IoT functions
                    {
                        "Effect": "Allow",
                        "Action": "iot:*",
                        "Resource": "*",
                    },
                    // Allow Greengrass Core to log to CloudWatch Logs
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:DescribeLogStreams"
                        ],
                        "Resource": [
                            "arn:aws:logs:*:*:*"
                        ]
                    },
                    // Allow other resources as needed
                ]
            },
        });

        // Functions to be used in the Greengrass Group Deployment
        const ggLambdaBASE = new GreengrassLambdaBASE(this, "GreengrassLambdaBASE", {
            functionName: id + '-GreengrassLambda-BASEe',
            stackName: id,
        });

        /*
        * This section pulls together all the Greengrass related definitions, and creates the Deployment
        */

        // Greengrass Core Definition
        const coreDefinition = new greengrass.CfnCoreDefinition(this, 'CoreDefinition', {
            name: 'StreamCore',
            initialVersion: {
                cores: [
                    {
                        certificateArn: crIoTResource.certificateArn,
                        id: '1',
                        thingArn: crIoTResource.thingArn
                    }
                ]
            }
        });

        // Create Greengrass Lambda Function definition - Placeholder for group deployment, contents
        // come from the function definition version
        const functionDefinition = new greengrass.CfnFunctionDefinition(this, 'FunctionDefinition', {
            name: 'GreengrassFunction'
        });
        // Create the Lambda function definition version from the definition above
        // Use the defaultConfig as "NoContainer" to allow for Connectors where isolation mode cannot be specified
        //@ts-ignore
        const functionDefinitionVersion = new greengrass.CfnFunctionDefinitionVersion(this, 'FunctionDefinitionVersion', {
            functionDefinitionId: functionDefinition.attrId,
            defaultConfig: {
                execution: {
                    // All functions run as processes since the deployment is targeted for container
                    isolationMode: "NoContainer",
                }
            },
            functions: [
                {
                    id: '1',
                    functionArn: ggLambdaBASE.greengrassLambdaAlias.functionArn,
                    functionConfiguration: {
                        encodingType: 'binary',
                        pinned: true,
                        timeout: 3,
                        environment: {
                        }
                    }
                },
            ]
        });

        const subscriptionDefinition = new greengrass.CfnSubscriptionDefinition(this, 'SubscriptionDefinition', {
            name: 'SubscriptionsDefinition',
            initialVersion: {
                subscriptions: [
                    // {
                    //     // Simulated sensor data published on topic 'sensor_data' and received by the producer Lambda
                    //     id: '1',
                    //     source: ggLambdaBASE.greengrassLambdaAlias.functionArn,
                    //     subject: 'base',
                    //     target: ggLambdaBASE.greengrassLambdaAlias.functionArn
                    // },
                ]
            }
        });

        const loggerDefinition = new greengrass.CfnLoggerDefinition(this, 'LoggerDefinition', {
            name: 'LoggerDefinition',
            initialVersion: {
                loggers: [
                    // Setup logging of system and lambda locally and cloud
                    {
                        id: '1',
                        component: "GreengrassSystem",
                        level: "INFO",
                        type: "FileSystem",
                        space: 1024
                    },
                    {
                        id: '2',
                        component: "Lambda",
                        level: "INFO",
                        type: "FileSystem",
                        space: 1024
                    },
                    {
                        id: '3',
                        component: "GreengrassSystem",
                        level: "WARN",
                        type: "AWSCloudWatch"
                    },
                    {
                        id: '4',
                        component: "Lambda",
                        level: "WARN",
                        type: "AWSCloudWatch"
                    }
                ]
            }
        });

        // Combine all definitions and create the Group
        const greengrassGroup = new greengrass.CfnGroup(this, 'GreengrassGroup', {
            name: id.split('-').join('_'),
            roleArn: ggServiceRole.roleArn,
            initialVersion: {
                coreDefinitionVersionArn: coreDefinition.attrLatestVersionArn,
                subscriptionDefinitionVersionArn: subscriptionDefinition.attrLatestVersionArn,
                loggerDefinitionVersionArn: loggerDefinition.attrLatestVersionArn,
                // resourceDefinitionVersionArn: resourceDefinition.attrLatestVersionArn,
                functionDefinitionVersionArn: functionDefinition.attrLatestVersionArn
            }
        });

        // Attach a custom resource to the Greengrass group to do a deployment reset before attempting to delete the group
        // Create Greengrass Service role with permissions the Core's resources should have
        const ggResetDeployment = new CustomResourceGreengrassResetDeployment(this, "GreengrassResetDeploymentResource", {
            functionName: id + '-GreengrassResetDeploymentFunction',
            stackName: id,
            greengrassGroup: id.split('-').join('_')
        });
        ggResetDeployment.node.addDependency(greengrassGroup);
    }
}

// Create stack
const app = new cdk.App();
new GreengrassBaseStack(app, 'greengrass-base-accel');
app.synth();
