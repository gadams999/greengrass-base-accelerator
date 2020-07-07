import * as cdk from "@aws-cdk/core";
import * as greengrass from "@aws-cdk/aws-greengrass";
import * as lambda from "@aws-cdk/aws-lambda";
// import * as secretsmanager from "@aws-cdk/aws-secretsmanager";
import { HelperIoTThingCertPolicy } from "./helper-iot-thing-cert-policy/helper-iot-thing-cert-policy";
import { CustomResourceGreengrassGroupRole } from "./cr-greengrass-group-role/cr-greengrass-group-role";
import { CustomResourceGreengrassResetDeployment } from "./cr-greengrass-reset-deployment/cr-greengrass-reset-deployment";
import { GreengrassLambda } from "./gg-lambda-helper/gg-lambda-helper";

/**
 * A stack that sets up a Greengrass Group and all support resources
 */
export class GreengrassBaseStack extends cdk.Stack {
    constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // // Secret used by Greengrass Lambda
        // // String's values (JSON key-value pairs) made available
        // const secret = new secretsmanager.CfnSecret(this, 'TestSecret', {
        //     name: "greengrass-mysecret",
        //     secretString: JSON.stringify({"foo": "bar"})
        // });

        // Policy for created thing (data plane operations)
        // the IoT resources should be scoped down as needed for Greengrass
        const iotPolicy = JSON.stringify({
            Version: "2012-10-17",
            Statement: [
                { Effect: "Allow", Action: "iot:*", Resource: "*" },
                { Effect: "Allow", Action: "greengrass:*", Resource: "*" },
            ],
        });

        // Create AWS IoT Thing/Certificate/Policy as basis for Greengrass Core
        const crIoTResource = new HelperIoTThingCertPolicy(
            this,
            "CreateThingCertPolicyCustomResource",
            {
                functionName: id + "-CreateThingCertPolicyFunction",
                iotThingName:
                    cdk.Stack.of(this).stackName.split("-").join("_") + "_Core",
                iotPolicy: iotPolicy,
            }
        );

        // Create Greengrass Service role with permissions the Core's resources should have
        const ggServiceRole = new CustomResourceGreengrassGroupRole(
            this,
            "GreengrassGroupRoleCustomResource",
            {
                functionName: id + "-GreengrassGroupRoleFunction",
                stackName: id,
                rolePolicy: {
                    Version: "2012-10-17",
                    Statement: [
                        // Allow All IoT functions
                        {
                            Effect: "Allow",
                            Action: "iot:*",
                            Resource: "*",
                        },
                        // Allow Greengrass Core to log to CloudWatch Logs
                        {
                            Effect: "Allow",
                            Action: [
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "logs:DescribeLogStreams",
                            ],
                            Resource: ["arn:aws:logs:*:*:*"],
                        },
                        // Allow other actions as needed
                    ],
                },
            }
        );

        // Functions to be used in the Greengrass Group Deployment
        // This uses the GreengrassLambda helper to create the function
        // specifically for Greengrass (no need for permissions, subset of
        // run times)
        const ggLambdaProducer = new GreengrassLambda(
            this,
            "GreengrassLambdaProducer",
            {
                functionName: "Lambda-Producer",
                stackName: id,
                assetPath: "lambda/producer",
                runTime: lambda.Runtime.PYTHON_3_7,
                handler: "producer.main",
            }
        );
        const ggLambdaConsumer = new GreengrassLambda(
            this,
            "GreengrassLambdaConsumer",
            {
                functionName: "Lambda-Consumer",
                stackName: id,
                assetPath: "lambda/consumer",
                runTime: lambda.Runtime.PYTHON_3_7,
                handler: "consumer.main",
            }
        );
        const ggLambdaReplay = new GreengrassLambda(
            this,
            "GreengrassLambdaReplay",
            {
                functionName: "Lambda-Replay",
                stackName: id,
                assetPath: "lambda/replay",
                runTime: lambda.Runtime.PYTHON_3_7,
                handler: "replay.main",
            }
        );

        /*
         * This section pulls together all the Greengrass related definitions, and creates the Deployment
         */

        // Greengrass Core Definition
        const coreDefinition = new greengrass.CfnCoreDefinition(
            this,
            "CoreDefinition",
            {
                name: "StreamCore",
                initialVersion: {
                    cores: [
                        {
                            certificateArn: crIoTResource.certificateArn,
                            id: "1",
                            thingArn: crIoTResource.thingArn,
                        },
                    ],
                },
            }
        );

        // Create Greengrass Lambda Function definition - Placeholder for group deployment, contents
        // come from the function definition version
        const functionDefinition = new greengrass.CfnFunctionDefinition(
            this,
            "FunctionDefinition",
            {
                name: id + "-GreengrassFunction",
            }
        );
        // Create the Lambda function definition version from the definition above
        // Use the defaultConfig as "NoContainer" to allow for Connectors where isolation mode cannot be specified
        //@ts-ignore
        const functionDefinitionVersion = new greengrass.CfnFunctionDefinitionVersion(
            this,
            "FunctionDefinitionVersion",
            {
                functionDefinitionId: functionDefinition.attrId,
                defaultConfig: {
                    execution: {
                        // All functions run as processes since the deployment is targeted for container
                        isolationMode: "NoContainer",
                    },
                },
                functions: [
                    {
                        // This enables the Stream Manager feature in Greengrass (core component such as Local Shadow)
                        id: "CoreFunction1",
                        functionArn:
                            "arn:aws:lambda:::function:GGStreamManager:1",
                        functionConfiguration: {
                            encodingType: "binary",
                            pinned: true,
                            timeout: 3,
                            environment: {
                                variables: {
                                    STREAM_MANAGER_AUTHENTICATE_CLIENT: "false",
                                },
                            },
                        },
                    },
                    {
                        id: "LambdaFunction1",
                        functionArn:
                            ggLambdaProducer.greengrassLambdaAlias.functionArn,
                        functionConfiguration: {
                            encodingType: "binary",
                            pinned: true,
                            timeout: 3,
                            environment: {
                                // This refers to the secret resource below, uncomment to affiliate
                                // resourceAccessPolicies: [
                                //     {
                                //         resourceId: "ResourceId1",
                                //         permission: "ro"
                                //     }
                                // ]
                            },
                        },
                    },
                    {
                        id: "LambdaFunction2",
                        functionArn:
                            ggLambdaConsumer.greengrassLambdaAlias.functionArn,
                        functionConfiguration: {
                            encodingType: "binary",
                            pinned: true,
                            timeout: 3,
                            environment: {},
                        },
                    },
                    {
                        id: "LambdaFunction3",
                        functionArn:
                            ggLambdaReplay.greengrassLambdaAlias.functionArn,
                        functionConfiguration: {
                            encodingType: "binary",
                            pinned: true,
                            timeout: 3,
                            environment: {},
                        },
                    },
                ],
            }
        );

        const subscriptionDefinition = new greengrass.CfnSubscriptionDefinition(
            this,
            "SubscriptionDefinition",
            {
                name: id + "-SubscriptionsDefinition",
                initialVersion: {
                    subscriptions: [
                        {
                            id: "Subscription1",
                            // See consumer messages in the cloud
                            source:
                                ggLambdaConsumer.greengrassLambdaAlias
                                    .functionArn,
                            subject: "test",
                            target: "cloud",
                        },
                        {
                            id: "Subscription2",
                            // trigger replay by send message to function
                            source: "cloud",
                            subject: "test",
                            target:
                                ggLambdaReplay.greengrassLambdaAlias
                                    .functionArn,
                        },
                    ],
                },
            }
        );

        const loggerDefinition = new greengrass.CfnLoggerDefinition(
            this,
            "LoggerDefinition",
            {
                name: id + "-LoggerDefinition",
                initialVersion: {
                    loggers: [
                        // Setup logging of system and lambda locally and cloud
                        {
                            id: "LoggerDefinition1",
                            component: "GreengrassSystem",
                            level: "INFO",
                            type: "FileSystem",
                            space: 1024,
                        },
                        {
                            id: "LoggerDefinition2",
                            component: "Lambda",
                            level: "INFO",
                            type: "FileSystem",
                            space: 1024,
                        },
                        {
                            id: "LoggerDefinition3",
                            component: "GreengrassSystem",
                            level: "WARN",
                            type: "AWSCloudWatch",
                        },
                        {
                            id: "LoggerDefinition4",
                            component: "Lambda",
                            level: "WARN",
                            type: "AWSCloudWatch",
                        },
                    ],
                },
            }
        );

        /**
         * This is an example resource definition for a cloud resource (secret manager). The secret definition
         * is at the top of this file and named "secret". Not the commented out environment for the base lambda
         * that affiliates the secret resource, "ResourceId1" with the lambda.
         */
        // const resourceDefinition = new greengrass.CfnResourceDefinition(this, 'ResourceDefinition', {
        //     name: id + "-ResourceDefinition",
        //     initialVersion: {
        //         resources: [
        //             {
        //                 id: 'ResourceId1',
        //                 name: "gg_secret",
        //                 resourceDataContainer: {
        //                     secretsManagerSecretResourceData: {
        //                         arn: secret.ref
        //                     }
        //                 }
        //             }
        //         ]
        //     }
        // });

        // Combine all definitions and create the Group
        const greengrassGroup = new greengrass.CfnGroup(
            this,
            "GreengrassGroup",
            {
                name: id.split("-").join("_"),
                roleArn: ggServiceRole.roleArn,
                initialVersion: {
                    coreDefinitionVersionArn:
                        coreDefinition.attrLatestVersionArn,
                    subscriptionDefinitionVersionArn:
                        subscriptionDefinition.attrLatestVersionArn,
                    loggerDefinitionVersionArn:
                        loggerDefinition.attrLatestVersionArn,
                    // resourceDefinitionVersionArn: resourceDefinition.attrLatestVersionArn,
                    functionDefinitionVersionArn:
                        functionDefinition.attrLatestVersionArn,
                },
            }
        );

        // Attach a custom resource to the Greengrass group to do a deployment reset before attempting to delete the group
        // Create Greengrass Service role with permissions the Core's resources should have
        const ggResetDeployment = new CustomResourceGreengrassResetDeployment(
            this,
            "GreengrassResetDeploymentResource",
            {
                functionName: id + "-GreengrassResetDeploymentFunction",
                stackName: id,
                greengrassGroup: id.split("-").join("_"),
            }
        );
        ggResetDeployment.node.addDependency(greengrassGroup);
    }
}
