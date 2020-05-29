import cfn = require('@aws-cdk/aws-cloudformation');
import lambda = require('@aws-cdk/aws-lambda');
import iam = require('@aws-cdk/aws-iam');
import cdk = require('@aws-cdk/core');
import uuid = require('uuid/v5');

export interface CustomResourceIoTThingCertPolicyProps {
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

export class CustomResourceIoTThingCertPolicy extends cdk.Construct {
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
   * @returns String values for `certificatePem`, `privateKeyPem`, `certificateArn`, `thingArn`, and `endpointDataAts` to be used as CloudFormation outputs.
   */
  public readonly certificatePem: string;
  public readonly privateKeyPem: string;
  public readonly certificateArn: string;
  public readonly thingArn: string;
  public readonly endpointDataAts: string;

  constructor(scope: cdk.Construct, id: string, props: CustomResourceIoTThingCertPolicyProps) {
    super(scope, id);
    props.physicalId = props.functionName;
    const resource = new cfn.CustomResource(this, 'Resource', {
      provider: cfn.CustomResourceProvider.fromLambda(new lambda.SingletonFunction(this, 'Singleton', {
        functionName: props.functionName,
        uuid: uuid(props.functionName, uuid.DNS),
        code: lambda.Code.fromAsset('cr-create-iot-thing-cert-policy/cr_iot_thing_cert_policy'),
        handler: 'index.main',
        timeout: cdk.Duration.seconds(30),
        runtime: lambda.Runtime.PYTHON_3_8,
        // Policy for Lambda to action on IoT resources - TODO - scope down to actions taken by Lambda
        initialPolicy: [
          new iam.PolicyStatement( {
              actions: [ 'iot:*' ],
              resources: [ '*' ]
          }),
          new iam.PolicyStatement( {
              actions: [
                'ssm:DeleteParameter',
                'ssm:GetParameter',
                'ssm:PutParameter'
              ],
              resources: [ '*' ]
          })
        ]
      })),
      properties: props
    });
    // Set resource return values for use by cdk.cfnOutput
    this.certificatePem = resource.getAttString('certificatePem');
    this.privateKeyPem = resource.getAttString('privateKeyPem');
    this.thingArn = resource.getAttString('thingArn');
    this.certificateArn = resource.getAttString('certificateArn');
    this.endpointDataAts = resource.getAttString('endpointDataAts')
  }
}

