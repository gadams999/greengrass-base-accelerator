import cdk = require('@aws-cdk/core');
import lambda = require('@aws-cdk/aws-lambda');

export class GreengrassLambdaBASEProps {
  /**
   * Resource properties used to construct the custom resource and passed as dictionary
   * to the resource as part of the "ResourceProperties". Note that the properties below
   * will have an uppercase first character and the rest of the property kept intact.
   * For example, physicalId will be passed as PhysicalId.
   * 
   * For a new Lambda function, replicate this construct and replace "BASE" with a unique name
   * e.g. the function FooBar would be:
   *     class GreengrassLambdaFooBar
   *     class GreengrassLambdaFooBar
   *     etc.
   */
  functionName: string;
  stackName: string;
}

export class GreengrassLambdaBASE extends cdk.Construct {
  public readonly greengrassLambdaAlias: lambda.Alias;

  constructor(scope: cdk.Construct, id: string, props: GreengrassLambdaBASEProps) {
    super(scope, id);
    // Create and Deploy Lambda for use by Greengrass
    const greengrassLambda = new lambda.Function(this, props.stackName + '-BASE', {
      runtime: lambda.Runtime.PYTHON_3_7,
      functionName: props.functionName,
      code: lambda.Code.fromAsset('lambda-gg-base/lambda_code'),
      handler: 'base.main',
    });
    const version = greengrassLambda.addVersion('FunctionVersionPlaceholder');

    // Greengrass Lambda specify the alias
    this.greengrassLambdaAlias = new lambda.Alias(this, props.stackName + '-GreengrassSampleAlias', {
      aliasName: 'PROD',
      version: version
    })
  }
}
