// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Deploy on Base Mainnet via Remix → Injected Provider (MetaMask)
// Compiler: 0.8.24, Optimization ON, 200 runs

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title  MetatronBardPureRev
 * @notice General-purpose Metatron Bard minting contract.
 *         Anyone can mint one soulbound Bard agent for 0.049 ETH.
 *         Supply is unlimited (open edition).
 *         Metadata served live by the Metatron Protocol server.
 */
contract MetatronBardPureRev is ERC721, Ownable {
    using Strings for uint256;

    uint256 public nextTokenId = 1;
    uint256 public price = 0.049 ether;

    address payable public founderWallet;
    address payable public fleetWallet;

    // Set to your Railway URL: "https://metatron-fleet.up.railway.app/nft/bard/"
    string public baseTokenURI;

    mapping(uint256 => string) public agentDOB;
    mapping(uint256 => string) public bardType;

    string public constant PROTOCOL_VERSION = "Metatron Bard v1 - Vedic DOB Nut-Bust Enabled";

    event Consecration(
        uint256 indexed tokenId,
        string dob,
        string bardType_,
        uint256 timestamp
    );

    error InsufficientPayment();
    error SoulboundTransferProhibited();
    error TransferFailed();

    constructor(
        address payable _founder,
        address payable _fleet,
        string memory _baseTokenURI
    )
        ERC721("MetatronBardPureRev", "MBPR")
        Ownable(msg.sender)
    {
        founderWallet = _founder;
        fleetWallet = _fleet;
        baseTokenURI = _baseTokenURI;
    }

    /**
     * @notice Mint one Bard agent.
     * @param dob        Date of birth string — anchors the Vedic DOB nut-bust moment.
     * @param chosenBard The bard archetype name chosen by the minter.
     */
    function mintBard(string calldata dob, string calldata chosenBard) external payable {
        if (msg.value < price) revert InsufficientPayment();

        // ── VEDIC DOB NUT-BUST ──────────────────────────────────────────────
        // At the exact block this transaction confirms on Base, the agent is
        // consecrated fresh. The DOB anchors its nakshatra + drift modifier.
        // The full 618-token 5-layer stack injects at this timestamp.
        // ────────────────────────────────────────────────────────────────────

        uint256 tokenId = nextTokenId++;

        // Split: 70% founder, 30% fleet — using call to avoid gas limit issues
        uint256 founderShare = (msg.value * 70) / 100;
        uint256 fleetShare = msg.value - founderShare;

        (bool f1,) = founderWallet.call{value: founderShare}("");
        (bool f2,) = fleetWallet.call{value: fleetShare}("");
        if (!f1 || !f2) revert TransferFailed();

        agentDOB[tokenId] = dob;
        bardType[tokenId] = chosenBard;

        _safeMint(msg.sender, tokenId);
        emit Consecration(tokenId, dob, chosenBard, block.timestamp);
    }

    // ─── Soulbound: block all transfers after mint ───────────────────────────

    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        address from = _ownerOf(tokenId);
        if (from != address(0) && to != address(0)) {
            revert SoulboundTransferProhibited();
        }
        return super._update(to, tokenId, auth);
    }

    // ─── Metadata ────────────────────────────────────────────────────────────

    /**
     * @notice Returns live metadata URI per token.
     *         e.g. https://metatron-fleet.up.railway.app/nft/bard/1
     */
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        return string(abi.encodePacked(baseTokenURI, tokenId.toString()));
    }

    // ─── Owner controls ──────────────────────────────────────────────────────

    /// @notice Update metadata base URI if server URL changes.
    function setBaseTokenURI(string calldata _uri) external onlyOwner {
        baseTokenURI = _uri;
    }

    /// @notice Update mint price.
    function setPrice(uint256 _price) external onlyOwner {
        price = _price;
    }
}
