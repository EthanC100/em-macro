#!/usr/bin/env bash
# Manage the horizons-norgate Windows server (Norgate futures data pipeline).
# See docs/infra/aws_norgate_server.md.
#
# Usage:
#   scripts/aws_server.sh start             # start the instance, print its new public IP
#   scripts/aws_server.sh stop              # stop the instance (stops compute charges)
#   scripts/aws_server.sh status            # state, type, public IP, allowed RDP sources
#   scripts/aws_server.sh allow-ip [IP]     # restrict RDP to IP/32 (default: this machine's public IP)
#
# The region is always passed explicitly: the server lives in ap-southeast-2 (Sydney),
# which differs from the Singapore default some environments set.
set -euo pipefail

REGION="ap-southeast-2"
INSTANCE_ID="${HORIZONS_INSTANCE_ID:-i-091fbf95cc5a6162a}"
SG_ID="${HORIZONS_SG_ID:-sg-0e77e6b03d0d9fdf8}"
RDP_PORT=3389

aws_() { aws --region "$REGION" "$@"; }

public_ip() {
  aws_ ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
}

cmd_start() {
  aws_ ec2 start-instances --instance-ids "$INSTANCE_ID" \
    --query 'StartingInstances[0].CurrentState.Name' --output text
  echo "Waiting for instance to be running..."
  aws_ ec2 wait instance-running --instance-ids "$INSTANCE_ID"
  echo "Running. Public IP: $(public_ip)  (changes on every start)"
}

cmd_stop() {
  aws_ ec2 stop-instances --instance-ids "$INSTANCE_ID" \
    --query 'StoppingInstances[0].CurrentState.Name' --output text
  echo "Waiting for instance to stop..."
  aws_ ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
  echo "Stopped. Compute billing has ended; the 60 GB disk is still billed while it exists."
}

cmd_status() {
  aws_ ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].{Id:InstanceId,State:State.Name,Type:InstanceType,PublicIp:PublicIpAddress,AZ:Placement.AvailabilityZone,Launched:LaunchTime}' \
    --output table
  echo "Allowed RDP sources (port $RDP_PORT):"
  aws_ ec2 describe-security-groups --group-ids "$SG_ID" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`$RDP_PORT\`].IpRanges[].CidrIp" --output text
}

cmd_allow_ip() {
  local ip="${1:-}"
  if [[ -z "$ip" ]]; then
    ip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
    echo "Detected this machine's public IP: $ip"
  fi
  ip="${ip%/32}"
  if ! [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "error: '$ip' is not an IPv4 address" >&2; exit 1
  fi

  # Remove every existing RDP rule, then add the single new /32.
  local old
  old="$(aws_ ec2 describe-security-groups --group-ids "$SG_ID" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`$RDP_PORT\`].IpRanges[].CidrIp" --output text)"
  for cidr in $old; do
    echo "Revoking $cidr"
    aws_ ec2 revoke-security-group-ingress --group-id "$SG_ID" \
      --protocol tcp --port "$RDP_PORT" --cidr "$cidr" >/dev/null
  done
  aws_ ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --ip-permissions "IpProtocol=tcp,FromPort=$RDP_PORT,ToPort=$RDP_PORT,IpRanges=[{CidrIp=$ip/32,Description=RDP}]" >/dev/null
  echo "RDP ($RDP_PORT) now allowed only from $ip/32"
}

case "${1:-}" in
  start)    cmd_start ;;
  stop)     cmd_stop ;;
  status)   cmd_status ;;
  allow-ip) shift; cmd_allow_ip "${1:-}" ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
