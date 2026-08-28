# SentraAura — PostgreSQL Failover Runbook

## Overview

This runbook covers manual and automated failover procedures for the Aurora PostgreSQL cluster used by SentraAura services.

## Architecture

- **Primary**: `sentra-<env>-writer` (read/write)
- **Readers**: `sentra-<env>-reader-1`, `sentra-<env>-reader-2` (read-only)
- **Endpoint**: Cluster endpoint automatically routes to primary
- **Multi-AZ**: Enabled in staging, canary, and production

## Automated Failover

Aurora automatically fails over to a reader in case of primary failure.
- **Detection time**: ~30 seconds
- **Failover time**: ~60-120 seconds
- **No data loss**: synchronous replication within AZ

## Manual Failover Procedure

### When to Use

- Aurora automatic failover did not occur
- Need to fail over for maintenance
- Primary instance is degraded but not failed

### Steps

1. **Identify target reader**
   ```bash
   aws rds describe-db-clusters \
     --db-cluster-identifier sentra-<env> \
     --query 'DBClusters[0].DBClusterMembers'
   ```

2. **Verify reader lag**
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier sentra-<env>-reader-1 \
     --query 'DBInstances[0].ReadReplicaDBInstanceIdentifiers'
   ```
   Lag should be < 5 seconds.

3. **Initiate failover**
   ```bash
   aws rds failover-db-cluster \
     --db-cluster-identifier sentra-<env> \
     --target-db-instance-identifier sentra-<env>-reader-1
   ```

4. **Monitor failover**
   ```bash
   watch -n 5 'aws rds describe-db-clusters \
     --db-cluster-identifier sentra-<env> \
     --query "DBClusters[0].Status"'
   ```
   Wait for status to return to `available`.

5. **Verify application connectivity**
   ```bash
   kubectl get pods --all-namespaces | grep -i error
   ```
   Check that services are reconnecting successfully.

6. **Update documentation**
   Record failover reason, time, and outcome in incident log.

## Force Failover (Data Loss Risk)

**Only use when automatic and manual failover both fail.**

1. **Promote reader to standalone**
   ```bash
   aws rds promote-read-replica \
     --db-instance-identifier sentra-<env>-reader-1
   ```

2. **Update application connection strings**
   ```bash
   kubectl patch secret sentra-db-credentials \
     --type=json \
     -p='[{"op": "replace", "path": "/data/host", "value":"<new-endpoint>"}]'
   ```

3. **Restart dependent services**
   ```bash
   kubectl rollout restart deployment -n sentra
   ```

## Recovery After Failover

1. **Investigate primary failure**
   - Check CloudWatch logs
   - Review RDS events
   - Check for resource exhaustion

2. **Rebuild failed instance**
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier sentra-<env>-writer \
     --db-cluster-identifier sentra-<env> \
     --db-instance-class db.r6g.xlarge \
     --engine aurora-postgresql
   ```

3. **Verify replication**
   ```sql
   SELECT * FROM pg_stat_replication;
   ```

## Prevention

- Enable Performance Insights
- Set up CloudWatch alarms for:
  - CPU > 80%
  - Memory < 20%
  - Connection count > 80% of max
  - Replication lag > 5 seconds
- Regular failover drills quarterly
