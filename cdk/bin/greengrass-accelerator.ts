#!/usr/bin/env node
import * as cdk from "@aws-cdk/core";
import { GreengrassBaseStack } from "../lib/greengrass-accelerator-stack";

const app = new cdk.App();
// Pull the stack name from the context. Alert if the stack name has not been set.
try {
    let x = app.node.tryGetContext("stack_name");
    if (x === "REPLACE_WITH_STACK_NAME") {
        console.error("The stack name needs to be defined in cdk.json");
        process.exit(1);
    }
    x = app.node.tryGetContext("region");
    if (x === "REPLACE_WITH_REGION_NAME") {
        console.error("The region name needs to be defined in cdk.json");
        process.exit(1);
    }
} catch (e) {
    console.log("error is", e);
}

new GreengrassBaseStack(app, app.node.tryGetContext("stack_name"), {
    env: {
        region: app.node.tryGetContext("region"),
    },
});
app.synth();