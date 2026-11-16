import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

aws_region = os.getenv("AWS_REGION_NAME", "us-east-1")
nova_model_id = os.getenv("NOVA_SONIC_PRO_MODEL_ID", "amazon.nova-pro-v1:0")
titan_model_id = os.getenv("TITAN_MODEL_ID", "amazon.titan-embed-text-v2:0")

print(f"Connecting to AWS Bedrock in region: {aws_region}...")

bedrock_runtime = boto3.client(
    service_name="bedrock-runtime",
    region_name=aws_region,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

# 1. Test Amazon Nova Pro (Converse API)
print(f"\n1. Testing Nova Pro ({nova_model_id})...")
try:
    response = bedrock_runtime.converse(
        modelId=nova_model_id,
        messages=[
            {
                "role": "user",
                "content": [{"text": "SRE verification ping: Respond with the single word 'PONG'."}]
            }
        ]
    )
    reply = response["output"]["message"]["content"][0]["text"].strip()
    print(f"   ✅ Nova Pro responded: {reply}")
except Exception as e:
    print(f"   ❌ Nova Pro call failed: {e}")

# 2. Test Titan Embeddings V2 (InvokeModel API)
print(f"\n2. Testing Titan Embeddings V2 ({titan_model_id})...")
try:
    body = json.dumps({"inputText": "Container checkout-service exited with code 137 (OOMKilled)."})
    response = bedrock_runtime.invoke_model(
        modelId=titan_model_id,
        body=body,
        contentType="application/json",
        accept="application/json"
    )
    response_body = json.loads(response["body"].read())
    embedding = response_body.get("embedding", [])
    print(f"   ✅ Titan generated vector of dimension: {len(embedding)}")
except Exception as e:
    print(f"   ❌ Titan Embeddings call failed: {e}")

print("\nSmoke test complete!")
