import * as lambda from "@aws-cdk/aws-lambda";
import * as cdk from "@aws-cdk/core";

// import * as path from "path";

/**
 * Greengrass Lambda Helper - Creates a Lambda for use by Greengrass
 * along with versioning the function.
 *
 * Derived function name based on stack_name + function_name
 *
 */

export class GreengrassLambdaProps {
    /**
     * Resource properties used to construct the custom resource and passed as dictionary
     * to the resource as part of the "ResourceProperties". Note that the properties below
     * will have an uppercase first character and the rest of the property kept intact.
     * For example, physicalId will be passed as PhysicalId.
     *
     */
    functionName: string;
    stackName: string;
    assetPath: string;
    runTime: lambda.Runtime;
    handler: string;
}

export class GreengrassLambda extends cdk.Construct {
    public readonly greengrassLambdaAlias: lambda.Alias;

    constructor(
        scope: cdk.Construct,
        id: string,
        props: GreengrassLambdaProps
    ) {
        super(scope, id);
        // Create and Deploy Lambda for use by Greengrass
        const greengrassLambda = new lambda.Function(this, props.functionName, {
            description: `Generated on: ${new Date().toISOString()}`,
            runtime: props.runTime,
            functionName: props.stackName + "-" + props.functionName,
            code: lambda.Code.fromAsset(
                props.assetPath
                // path.join(__dirname, props.assetPath)
            ),
            handler: props.handler,
        });
        const version = greengrassLambda.addVersion(new Date().toISOString());
        // Greengrass Lambda specify the alias
        this.greengrassLambdaAlias = new lambda.Alias(
            this,
            props.stackName + "-GreengrassSampleAlias",
            {
                aliasName: "PROD",
                version: version,
            }
        );
    }
}
