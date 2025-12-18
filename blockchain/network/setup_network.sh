#!/bin/bash
# Hyperledger Fabric Network Setup Script
# setup_network.sh - Automated network deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Synthetic Data Audit Trail Network   ${NC}"
echo -e "${GREEN}  Hyperledger Fabric Setup Script      ${NC}"
echo -e "${GREEN}========================================${NC}"

# Configuration
CHANNEL_NAME="auditchannel"
CHAINCODE_NAME="audit_trail"
CHAINCODE_VERSION="1.0"
CHAINCODE_SEQUENCE="1"
FABRIC_CFG_PATH=$PWD

# Function to print status
print_status() {
    echo -e "${YELLOW}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker found"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    print_success "Docker Compose found"
    
    # Check if Fabric binaries exist
    if ! command -v cryptogen &> /dev/null; then
        print_error "Fabric binaries not found. Please install Hyperledger Fabric."
        echo "Run: curl -sSL https://bit.ly/2ysbOFE | bash -s"
        exit 1
    fi
    print_success "Fabric binaries found"
}

# Generate crypto materials
generate_crypto() {
    print_status "Generating crypto materials..."
    
    # Remove old crypto materials
    rm -rf crypto-config
    
    # Generate new crypto materials
    cryptogen generate --config=./crypto-config.yaml
    
    if [ $? -eq 0 ]; then
        print_success "Crypto materials generated"
    else
        print_error "Failed to generate crypto materials"
        exit 1
    fi
}

# Generate channel artifacts
generate_artifacts() {
    print_status "Generating channel artifacts..."
    
    # Create artifacts directory
    mkdir -p channel-artifacts
    
    # Set config path
    export FABRIC_CFG_PATH=$PWD
    
    # Generate genesis block
    configtxgen -profile AuditOrdererGenesis -channelID system-channel -outputBlock ./channel-artifacts/genesis.block
    
    if [ $? -ne 0 ]; then
        print_error "Failed to generate genesis block"
        exit 1
    fi
    print_success "Genesis block created"
    
    # Generate channel transaction
    configtxgen -profile AuditChannel -outputCreateChannelTx ./channel-artifacts/${CHANNEL_NAME}.tx -channelID $CHANNEL_NAME
    
    if [ $? -ne 0 ]; then
        print_error "Failed to generate channel transaction"
        exit 1
    fi
    print_success "Channel transaction created"
    
    # Generate anchor peer transactions
    configtxgen -profile AuditChannel -outputAnchorPeersUpdate ./channel-artifacts/HospitalMSPanchors.tx -channelID $CHANNEL_NAME -asOrg HospitalMSP
    configtxgen -profile AuditChannel -outputAnchorPeersUpdate ./channel-artifacts/RegulatorMSPanchors.tx -channelID $CHANNEL_NAME -asOrg RegulatorMSP
    configtxgen -profile AuditChannel -outputAnchorPeersUpdate ./channel-artifacts/ResearchMSPanchors.tx -channelID $CHANNEL_NAME -asOrg ResearchMSP
    
    print_success "Anchor peer transactions created"
}

# Start the network
start_network() {
    print_status "Starting Fabric network..."
    
    # Start containers
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        print_success "Network containers started"
    else
        print_error "Failed to start network"
        exit 1
    fi
    
    # Wait for containers to be ready
    print_status "Waiting for containers to be ready..."
    sleep 10
}

# Create and join channel
create_channel() {
    print_status "Creating channel: $CHANNEL_NAME..."
    
    # Create channel
    docker exec cli peer channel create \
        -o orderer.audit.com:7050 \
        -c $CHANNEL_NAME \
        -f /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.tx \
        --outputBlock /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block \
        --tls \
        --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/audit.com/orderers/orderer.audit.com/msp/tlscacerts/tlsca.audit.com-cert.pem
    
    if [ $? -eq 0 ]; then
        print_success "Channel created"
    else
        print_error "Failed to create channel"
        exit 1
    fi
}

# Join peers to channel
join_channel() {
    print_status "Joining peers to channel..."
    
    # Join Hospital peer
    docker exec cli peer channel join \
        -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block
    print_success "Hospital peer joined"
    
    # Join Regulator peer
    docker exec -e CORE_PEER_ADDRESS=peer0.regulator.audit.com:8051 \
        -e CORE_PEER_LOCALMSPID=RegulatorMSP \
        -e CORE_PEER_TLS_ROOTCERT_FILE=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/regulator.audit.com/peers/peer0.regulator.audit.com/tls/ca.crt \
        -e CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/regulator.audit.com/users/Admin@regulator.audit.com/msp \
        cli peer channel join \
        -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block
    print_success "Regulator peer joined"
    
    # Join Research peer
    docker exec -e CORE_PEER_ADDRESS=peer0.research.audit.com:9051 \
        -e CORE_PEER_LOCALMSPID=ResearchMSP \
        -e CORE_PEER_TLS_ROOTCERT_FILE=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/research.audit.com/peers/peer0.research.audit.com/tls/ca.crt \
        -e CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/research.audit.com/users/Admin@research.audit.com/msp \
        cli peer channel join \
        -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block
    print_success "Research peer joined"
}

# Deploy chaincode
deploy_chaincode() {
    print_status "Deploying chaincode..."
    
    # Package chaincode (for Go chaincode)
    docker exec cli peer lifecycle chaincode package ${CHAINCODE_NAME}.tar.gz \
        --path /opt/gopath/src/github.com/chaincode \
        --lang golang \
        --label ${CHAINCODE_NAME}_${CHAINCODE_VERSION}
    
    print_success "Chaincode packaged"
    
    # Install on all peers
    docker exec cli peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz
    print_success "Chaincode installed on Hospital peer"
    
    # Get package ID
    PACKAGE_ID=$(docker exec cli peer lifecycle chaincode queryinstalled | grep ${CHAINCODE_NAME}_${CHAINCODE_VERSION} | awk '{print $3}' | sed 's/,$//')
    
    # Approve for organizations
    docker exec cli peer lifecycle chaincode approveformyorg \
        -o orderer.audit.com:7050 \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        --version $CHAINCODE_VERSION \
        --package-id $PACKAGE_ID \
        --sequence $CHAINCODE_SEQUENCE \
        --tls \
        --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/audit.com/orderers/orderer.audit.com/msp/tlscacerts/tlsca.audit.com-cert.pem
    
    print_success "Chaincode approved by Hospital"
    
    # Commit chaincode
    docker exec cli peer lifecycle chaincode commit \
        -o orderer.audit.com:7050 \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        --version $CHAINCODE_VERSION \
        --sequence $CHAINCODE_SEQUENCE \
        --tls \
        --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/audit.com/orderers/orderer.audit.com/msp/tlscacerts/tlsca.audit.com-cert.pem
    
    print_success "Chaincode committed"
}

# Stop the network
stop_network() {
    print_status "Stopping network..."
    docker-compose down -v
    print_success "Network stopped"
}

# Clean up
cleanup() {
    print_status "Cleaning up..."
    docker-compose down -v
    rm -rf crypto-config channel-artifacts
    docker volume prune -f
    print_success "Cleanup complete"
}

# Print network info
print_network_info() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  Network Started Successfully!         ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "\n${YELLOW}Network Components:${NC}"
    echo "  - Orderer: orderer.audit.com:7050"
    echo "  - Hospital Peer: peer0.hospital.audit.com:7051"
    echo "  - Regulator Peer: peer0.regulator.audit.com:8051"
    echo "  - Research Peer: peer0.research.audit.com:9051"
    echo "  - Channel: $CHANNEL_NAME"
    echo "  - Chaincode: $CHAINCODE_NAME"
    echo -e "\n${YELLOW}CA Services:${NC}"
    echo "  - Hospital CA: localhost:7054"
    echo "  - Regulator CA: localhost:8054"
    echo "  - Research CA: localhost:9054"
    echo -e "\n${YELLOW}Useful Commands:${NC}"
    echo "  View logs: docker-compose logs -f"
    echo "  Stop network: ./setup_network.sh stop"
    echo "  Clean up: ./setup_network.sh cleanup"
}

# Main script logic
case "$1" in
    "start")
        check_prerequisites
        generate_crypto
        generate_artifacts
        start_network
        create_channel
        join_channel
        deploy_chaincode
        print_network_info
        ;;
    "stop")
        stop_network
        ;;
    "cleanup")
        cleanup
        ;;
    "restart")
        stop_network
        start_network
        ;;
    *)
        echo "Usage: $0 {start|stop|cleanup|restart}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the Fabric network"
        echo "  stop    - Stop the network"
        echo "  cleanup - Stop network and remove all artifacts"
        echo "  restart - Restart the network"
        exit 1
        ;;
esac
