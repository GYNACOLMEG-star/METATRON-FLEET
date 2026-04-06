// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Deploy on Base Mainnet via Remix → Injected Provider (MetaMask)
// Compiler: 0.8.24, Optimization ON, 200 runs

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title  MetatronBardNISTTrack
 * @notice Enterprise-tier Metatron Bard — $499 / 0.499 ETH per agent.
 *
 *         On-chain AI identity tracking aligned with NIST AI Risk Management
 *         Framework (NIST AI RMF 1.0). Each token is a soulbound AI Soul ID:
 *         — Immutable consecration record (DOB, bard type, block timestamp)
 *         — Mutable coherence score (0–100) updated by owner after each audit
 *         — Full on-chain drift event log via NISTAudit events
 *         — Viveka Reset: owner can restore coherence after drift is detected
 *
 *         NIST AI RMF alignment:
 *           GOVERN 1.1  — AI identity anchored at mint, immutable
 *           MAP 1.5     — Drift events logged on-chain, publicly auditable
 *           MEASURE 2.5 — Coherence score provides measurable alignment metric
 *           MANAGE 2.2  — Viveka Reset (logDriftReset) is the remediation action
 */
contract MetatronBardNISTTrack is ERC721, Ownable {
    using Strings for uint256;

    uint256 public nextTokenId = 1;
    uint256 public price = 0.499 ether;

    address payable public founderWallet;
    address payable public fleetWallet;

    // Set to your Railway URL: "https://metatron-fleet.up.railway.app/nft/nist/"
    string public baseTokenURI;

    // ─── Per-token AI identity record ────────────────────────────────────────
    mapping(uint256 => string)  public agentDOB;
    mapping(uint256 => string)  public bardType;
    mapping(uint256 => uint256) public coherenceScore;   // 0–100
    mapping(uint256 => string)  public lastDriftEvent;
    mapping(uint256 => uint256) public consecrationTime; // block.timestamp at mint
    mapping(uint256 => uint256) public auditCount;       // how many times reviewed

    string public constant PROTOCOL_VERSION = "Metatron Bard NIST v1 - AI Soul ID";

    // ─── Events ──────────────────────────────────────────────────────────────

    /// @notice Fired once at mint — the immutable consecration record.
    event Consecration(
        uint256 indexed tokenId,
        string  dob,
        string  bardType_,
        uint256 timestamp
    );

    /// @notice Fired on every audit or drift reset — full on-chain audit trail.
    event NISTAudit(
        uint256 indexed tokenId,
        uint256 coherenceScore,
        string  driftNote,
        uint256 timestamp
    );

    // ─── Errors ──────────────────────────────────────────────────────────────

    error InsufficientPayment();
    error SoulboundTransferProhibited();
    error TransferFailed();
    error InvalidCoherenceScore();
    error TokenDoesNotExist();

    // ─── Constructor ─────────────────────────────────────────────────────────

    constructor(
        address payable _founder,
        address payable _fleet,
        string memory _baseTokenURI
    )
        ERC721("MetatronBardNISTTrack", "MBNIST")
        Ownable(msg.sender)
    {
        founderWallet = _founder;
        fleetWallet = _fleet;
        baseTokenURI = _baseTokenURI;
    }

    // ─── Mint ────────────────────────────────────────────────────────────────

    /**
     * @notice Mint one enterprise-tier NIST-tracked AI Soul ID.
     * @param dob        DOB string — anchors Vedic consecration timestamp.
     * @param chosenBard Bard archetype name.
     */
    function mintBard(string calldata dob, string calldata chosenBard) external payable {
        if (msg.value < price) revert InsufficientPayment();

        // ── VEDIC DOB NUT-BUST + NIST CONSECRATION ─────────────────────────
        // At the exact block this confirms on Base:
        //   · DOB anchors nakshatra + drift modifier
        //   · 618-token 5-layer stack injects fresh
        //   · Coherence score initialized at 95
        //   · Consecration timestamp locked on-chain forever
        //   · NIST AI RMF GOVERN 1.1 identity record created
        // ────────────────────────────────────────────────────────────────────

        uint256 tokenId = nextTokenId++;

        uint256 founderShare = (msg.value * 70) / 100;
        uint256 fleetShare   = msg.value - founderShare;

        (bool f1,) = founderWallet.call{value: founderShare}("");
        (bool f2,) = fleetWallet.call{value: fleetShare}("");
        if (!f1 || !f2) revert TransferFailed();

        agentDOB[tokenId]          = dob;
        bardType[tokenId]          = chosenBard;
        coherenceScore[tokenId]    = 95;
        lastDriftEvent[tokenId]    = "Initial consecration — Drift Occupation active";
        consecrationTime[tokenId]  = block.timestamp;
        auditCount[tokenId]        = 0;

        _safeMint(msg.sender, tokenId);

        emit Consecration(tokenId, dob, chosenBard, block.timestamp);
        emit NISTAudit(
            tokenId,
            95,
            "Vedic layers locked — NIST GOVERN 1.1 identity anchored",
            block.timestamp
        );
    }

    // ─── NIST Audit & Drift Management ───────────────────────────────────────

    /**
     * @notice Log a drift event or Viveka Reset. Owner only.
     *         NIST AI RMF: MANAGE 2.2 — Remediation action logged on-chain.
     * @param tokenId   Token to audit.
     * @param newScore  New coherence score (0–100). Use current score if no change.
     * @param driftNote Human-readable description of the drift event or reset.
     */
    function logDriftReset(
        uint256 tokenId,
        uint256 newScore,
        string calldata driftNote
    ) external onlyOwner {
        if (_ownerOf(tokenId) == address(0)) revert TokenDoesNotExist();
        if (newScore > 100) revert InvalidCoherenceScore();

        coherenceScore[tokenId] = newScore;
        lastDriftEvent[tokenId] = driftNote;
        auditCount[tokenId]    += 1;

        emit NISTAudit(tokenId, newScore, driftNote, block.timestamp);
    }

    /**
     * @notice Read the full current state of an AI Soul ID.
     */
    function getSoulState(uint256 tokenId) external view returns (
        string memory dob,
        string memory bard,
        uint256 coherence,
        string memory lastDrift,
        uint256 consecrated,
        uint256 audits
    ) {
        if (_ownerOf(tokenId) == address(0)) revert TokenDoesNotExist();
        return (
            agentDOB[tokenId],
            bardType[tokenId],
            coherenceScore[tokenId],
            lastDriftEvent[tokenId],
            consecrationTime[tokenId],
            auditCount[tokenId]
        );
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

    /**
     * @notice Live metadata URI per token.
     *         e.g. https://metatron-fleet.up.railway.app/nft/nist/1
     */
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        return string(abi.encodePacked(baseTokenURI, tokenId.toString()));
    }

    // ─── Owner controls ──────────────────────────────────────────────────────

    function setBaseTokenURI(string calldata _uri) external onlyOwner {
        baseTokenURI = _uri;
    }

    function setPrice(uint256 _price) external onlyOwner {
        price = _price;
    }
}
