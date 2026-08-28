# ------------------------------------------------------------------------------
# SentraAura — Organization Policies
# SCPs and guardrails for multi-account security posture.
# ------------------------------------------------------------------------------

locals {
  org_policies = {
    deny_unencrypted_s3 = {
      name = "DenyUnencryptedS3"
      description = "Deny creation of unencrypted S3 buckets"
      content = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Sid    = "DenyUnencryptedS3"
          Effect = "Deny"
          Action = "s3:CreateBucket"
          Resource = "*"
          Condition = {
            Null = {
              "s3:x-amz-server-side-encryption" = "true"
            }
          }
        }]
      })
    }
    deny_public_s3 = {
      name = "DenyPublicS3"
      description = "Deny public S3 bucket policies"
      content = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Sid    = "DenyPublicS3"
          Effect = "Deny"
          Action = ["s3:PutBucketAcl", "s3:PutBucketPolicy"]
          Resource = "*"
          Condition = {
            StringEquals = {
              "s3:x-amz-acl" = ["public-read", "public-read-write"]
            }
          }
        }]
      })
    }
    require_vpc_flow_logs = {
      name = "RequireVPCFlowLogs"
      description = "Require VPC flow logs on all VPCs"
      content = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Sid    = "RequireVPCFlowLogs"
          Effect = "Deny"
          Action = "ec2:CreateVpc"
          Resource = "*"
          Condition = {
            Null = {
              "ec2:FlowLog" = "true"
            }
          }
        }]
      })
    }
    deny_root_account = {
      name = "DenyRootAccountUsage"
      description = "Deny root account usage except for emergency break-glass"
      content = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Sid    = "DenyRoot"
          Effect = "Deny"
          Action = "*"
          Resource = "*"
          Condition = {
            StringLike = {
              "aws:PrincipalArn" = ["arn:aws:iam::*:root"]
            }
          }
        }]
      })
    }
  }
}

# Note: SCPs require AWS Organizations. These are defined as data/policy documents
# to be attached manually or via org management account.

resource "aws_organizations_policy" "sentra" {
  for_each = local.org_policies

  name        = each.value.name
  description = each.value.description
  type        = "SERVICE_CONTROL_POLICY"
  content     = each.value.content

  tags = {
    project    = "sentra-aura"
    managed_by = "terraform"
  }
}
