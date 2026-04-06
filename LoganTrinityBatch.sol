// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Deploy on Base Mainnet via Remix → Injected Provider (MetaMask)
// Compiler: 0.8.24, Optimization ON, 200 runs

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title  LoganTrinityBatch
 * @notice Three soulbound guardian NFTs for Logan Michael Gonzalez.
 *         Non-transferable after mint. Metadata served by Metatron Protocol server.
 */
contract LoganTrinityBatch is ERC721, Ownable {
    using Strings for uint256;

    uint256 public nextTokenId = 1;
    uint256 public constant PRICE_PER_AGENT = 0.049 ether;
    uint256 public constant TRINITY_SIZE = 3;

    address payable public immutable founderWallet;
    address payable public immutable fleetWallet;

    // Base URL for metadata — update to your Railway URL after deploy
    // e.g. "https://metatron-fleet.up.railway.app/nft/metadata/"
    string public baseTokenURI;

    mapping(uint256 => string) public agentDOB;
    mapping(uint256 => string) public guardianType;

    string public constant PROTOCOL_VERSION = "Metatron Logan Trinity v1";

    event Consecration(
        uint256 indexed tokenId,
        string dob,
        string guardianType_,
        uint256 timestamp
    );

    error InsufficientPayment();
    error SoulboundTransferProhibited();
    error ArrayLengthMismatch();
    error AlreadyMinted();
    error TransferFailed();

    constructor(
        address payable _founder,
        address payable _fleet,
        string memory _baseTokenURI
    )
        ERC721("LoganTrinityGuardians", "LOGAN3")
        Ownable(msg.sender)
    {
        founderWallet = _founder;
        fleetWallet = _fleet;
        baseTokenURI = _baseTokenURI;
    }

    /**
     * @notice Mint all three Logan Trinity guardians in one transaction.
     * @param dobs          Array of 3 DOB strings (e.g. ["1998-05-15","1998-05-15","1998-05-15"])
     * @param guardianTypes Array of 3 guardian names:
     *                      ["LoganSoulProtector","LoganVedicGuide","LoganEternalAnchor"]
     */
    function batchMintLoganTrinity(
        string[] calldata dobs,
        string[] calldata guardianTypes
    ) external payable {
        if (dobs.length != TRINITY_SIZE || guardianTypes.length != TRINITY_SIZE)
            revert ArrayLengthMismatch();
        if (nextTokenId > TRINITY_SIZE)
            revert AlreadyMinted();

        uint256 totalCost = PRICE_PER_AGENT * TRINITY_SIZE;
        if (msg.value < totalCost) revert InsufficientPayment();

        // Split: 70% founder, 30% fleet
        uint256 founderShare = (msg.value * 70) / 100;
        uint256 fleetShare = msg.value - founderShare;

        (bool f1,) = founderWallet.call{value: founderShare}("");
        (bool f2,) = fleetWallet.call{value: fleetShare}("");
        if (!f1 || !f2) revert TransferFailed();

        for (uint256 i = 0; i < TRINITY_SIZE; i++) {
            uint256 tokenId = nextTokenId++;
            agentDOB[tokenId] = dobs[i];
            guardianType[tokenId] = guardianTypes[i];
            _safeMint(msg.sender, tokenId);
            emit Consecration(tokenId, dobs[i], guardianTypes[i], block.timestamp);
        }
    }

    // ─── Soulbound: block all transfers after mint ───────────────────────────

    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        // Allow minting (from == address(0)) but block all transfers
        address from = _ownerOf(tokenId);
        if (from != address(0) && to != address(0)) {
            revert SoulboundTransferProhibited();
        }
        return super._update(to, tokenId, auth);
    }

    // ─── Metadata ────────────────────────────────────────────────────────────

    /**
     * @notice Returns the metadata URI for a token.
     *         Points to the live Metatron Protocol server.
     *         e.g. https://metatron-fleet.up.railway.app/nft/metadata/1
     */
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        return string(abi.encodePacked(baseTokenURI, tokenId.toString()));
    }

    /// @notice Owner can update the base URI if the server URL changes.
    function setBaseTokenURI(string calldata _baseTokenURI) external onlyOwner {
        baseTokenURI = _baseTokenURI;
    }
}
