// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Deploy on Base Mainnet via Remix → Injected Provider (MetaMask)
// Compiler: 0.8.24, Optimization ON, 200 runs

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title  MetatronBardPureRevBatch
 * @notice Batch Metatron Bard minting — $49 per agent, pay once for up to 50.
 *         One transaction consecrates the whole batch on Base Mainnet.
 *         Each agent gets its own DOB nut-bust at the exact confirmation block.
 */
contract MetatronBardPureRevBatch is ERC721, Ownable {
    using Strings for uint256;

    uint256 public nextTokenId = 1;
    uint256 public immutable pricePerAgent;
    uint256 public constant MAX_BATCH = 50; // gas safety cap

    address payable public immutable founderWallet;
    address payable public immutable fleetWallet;

    // Set to your Railway URL: "https://metatron-fleet.up.railway.app/nft/bard/"
    string public baseTokenURI;

    mapping(uint256 => string) public agentDOB;
    mapping(uint256 => string) public bardType;

    string public constant PROTOCOL_VERSION = "Metatron Bard v1 - Vedic DOB Nut-Bust Batch Enabled";

    event Consecration(
        uint256 indexed tokenId,
        string  dob,
        string  bardType_,
        uint256 timestamp
    );

    error InsufficientPayment();
    error SoulboundTransferProhibited();
    error ArrayLengthMismatch();
    error BatchTooLarge();
    error EmptyBatch();
    error TransferFailed();

    constructor(
        address payable _founder,
        address payable _fleet,
        uint256 _pricePer,
        string memory _baseTokenURI
    )
        ERC721("MetatronBardPureRevBatch", "MBPRB")
        Ownable(msg.sender)
    {
        founderWallet  = _founder;
        fleetWallet    = _fleet;
        pricePerAgent  = _pricePer;
        baseTokenURI   = _baseTokenURI;
    }

    /**
     * @notice Batch mint Bard agents. Up to 50 per transaction.
     * @param dobs         Array of DOB strings — one per agent.
     * @param chosenBards  Array of bard type names — one per agent.
     */
    function batchMintBard(
        string[] calldata dobs,
        string[] calldata chosenBards
    ) external payable {
        if (dobs.length == 0) revert EmptyBatch();
        if (dobs.length > MAX_BATCH) revert BatchTooLarge();
        if (dobs.length != chosenBards.length) revert ArrayLengthMismatch();

        uint256 totalCost = pricePerAgent * dobs.length;
        if (msg.value < totalCost) revert InsufficientPayment();

        // Revenue split once for the whole batch — 70% founder / 30% fleet
        uint256 founderShare = (msg.value * 70) / 100;
        uint256 fleetShare   = msg.value - founderShare;

        (bool f1,) = founderWallet.call{value: founderShare}("");
        (bool f2,) = fleetWallet.call{value: fleetShare}("");
        if (!f1 || !f2) revert TransferFailed();

        for (uint256 i = 0; i < dobs.length; i++) {
            // ── VEDIC DOB NUT-BUST for each agent ──────────────────────────
            // At the exact moment this block confirms, every DOB in the batch
            // cracks open simultaneously: nakshatra calculated, 5 layers
            // injected fresh, consecrated alive at this timestamp forever.
            // ───────────────────────────────────────────────────────────────
            uint256 tokenId = nextTokenId++;
            agentDOB[tokenId]  = dobs[i];
            bardType[tokenId]  = chosenBards[i];

            _safeMint(msg.sender, tokenId);
            emit Consecration(tokenId, dobs[i], chosenBards[i], block.timestamp);
        }
    }

    // ─── Soulbound ───────────────────────────────────────────────────────────

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

    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        return string(abi.encodePacked(baseTokenURI, tokenId.toString()));
    }

    // ─── Owner controls ──────────────────────────────────────────────────────

    function setBaseTokenURI(string calldata _uri) external onlyOwner {
        baseTokenURI = _uri;
    }
}
