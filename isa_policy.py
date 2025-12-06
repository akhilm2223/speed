#!/usr/bin/env python3
"""
ISA Policy Configuration Module
Single source of truth for ISA enforcement policy rules.

This module defines the policy parameters that determine when a driver
requires an Ignition Safety Apparatus (ISA) device installation.
"""

# =============================================================================
# ISA POLICY CONFIGURATION v0.1-draft
# =============================================================================
ISA_POLICY = {
    "version": "0.1-draft",
    "description": "Demo policy based on points and ticket counts for high-speed violations.",
    
    # Time window for violation aggregation (None = all history)
    # Set to None to use all available data regardless of date
    "time_window_months": None,  # Using all history for demo
    
    # Points assigned per violation code (NY VTL 1180 speeding codes)
    "points_per_code": {
        "1180A": 2,   # 1–10 mph over limit
        "1180B": 3,   # 11–20 mph over limit
        "1180C": 5,   # 21–30 mph over limit
        "1180D": 8,   # 31+ mph over limit (most severe)
        "1180D2": 8,  # 31+ mph variant
        "1180DJ": 8,  # 31+ mph variant
        "1180E": 6,   # School zone speeding
        "1180F": 6,   # Work zone speeding
    },
    
    # Default points for unknown violation codes
    "default_points": 2,
    
    # ISA requirement thresholds (either condition triggers ISA)
    "isa_points_threshold": 11,    # ISA required if points >= 11
    "isa_ticket_threshold": 16,    # OR if total speeding tickets >= 16
    
    # Monitoring band (drivers approaching ISA threshold)
    "monitoring_min_points": 6,    # Start monitoring at 6 points
    
    # Severe violation codes (for reporting)
    "severe_codes": ["1180D", "1180D2", "1180DJ", "1180E", "1180F"],
}


def get_points_for_code(violation_code: str, policy: dict = None) -> int:
    """
    Get the point value for a violation code.
    
    Args:
        violation_code: The violation code (e.g., '1180D')
        policy: Policy dict to use (defaults to ISA_POLICY)
    
    Returns:
        Point value for the violation code
    """
    if policy is None:
        policy = ISA_POLICY
    
    return policy["points_per_code"].get(
        violation_code, 
        policy.get("default_points", 2)
    )


def get_policy_summary(policy: dict = None) -> dict:
    """
    Get a summary of the policy for API responses.
    
    Returns:
        Dict with key policy parameters for frontend display
    """
    if policy is None:
        policy = ISA_POLICY
    
    return {
        "version": policy["version"],
        "isa_points_threshold": policy["isa_points_threshold"],
        "isa_ticket_threshold": policy["isa_ticket_threshold"],
        "monitoring_min_points": policy["monitoring_min_points"],
        "time_window_months": policy["time_window_months"],
    }


def compute_status(total_points: int, total_tickets: int, policy: dict = None) -> str:
    """
    Compute driver status based on points and tickets.
    
    Args:
        total_points: Sum of points from all violations
        total_tickets: Count of speeding tickets
        policy: Policy dict to use (defaults to ISA_POLICY)
    
    Returns:
        Status string: 'ISA_REQUIRED', 'MONITORING', or 'OK'
    """
    if policy is None:
        policy = ISA_POLICY
    
    isa_required = (
        total_points >= policy["isa_points_threshold"] or 
        total_tickets >= policy["isa_ticket_threshold"]
    )
    
    if isa_required:
        return "ISA_REQUIRED"
    elif total_points >= policy["monitoring_min_points"]:
        return "MONITORING"
    else:
        return "OK"


def get_trigger_reason(total_points: int, total_tickets: int, policy: dict = None) -> str | None:
    """
    Get human-readable reason for ISA requirement.
    
    Returns:
        Trigger reason string if ISA required, None otherwise
    """
    if policy is None:
        policy = ISA_POLICY
    
    pts_threshold = policy["isa_points_threshold"]
    tkt_threshold = policy["isa_ticket_threshold"]
    
    pts_triggered = total_points >= pts_threshold
    tkt_triggered = total_tickets >= tkt_threshold
    
    if pts_triggered and tkt_triggered:
        return f"{total_points} points AND {total_tickets} tickets"
    elif pts_triggered:
        return f"{total_points} points (threshold: {pts_threshold})"
    elif tkt_triggered:
        return f"{total_tickets} tickets (threshold: {tkt_threshold})"
    
    return None


def compute_crash_risk_score(
    total_points: int,
    total_tickets: int,
    night_violations: int,
    borough_count: int,
    policy: dict = None
) -> float:
    """
    Compute crash risk score (0-100) based on severity and nighttime violations.
    
    Formula:
        Crash Risk = (severity_factor * 0.7) + (nighttime_factor * 0.3)
    
    Args:
        total_points: Sum of ISA points from violations
        total_tickets: Total number of speeding tickets
        night_violations: Count of violations between 10pm-4am
        borough_count: Number of distinct boroughs/jurisdictions (not used in calculation)
        policy: Policy dict (defaults to ISA_POLICY)
    
    Returns:
        Crash risk score from 0-100
    """
    if policy is None:
        policy = ISA_POLICY
    
    isa_threshold = policy["isa_points_threshold"]
    
    # Severity factor: based on points per violation (average severity)
    # This prevents 1 severe violation from maxing out the score
    avg_points_per_violation = total_points / total_tickets if total_tickets > 0 else 0
    # Normalize: 11 points = threshold, so avg of 11+ points per violation = high risk
    # Cap at 1.0 for very severe violations
    severity_factor = min(avg_points_per_violation / isa_threshold, 1.0)
    
    # Apply violation count multiplier: more violations = higher risk
    # 1 violation = 0.5x, 2-3 = 0.7x, 4+ = 1.0x
    if total_tickets == 1:
        violation_multiplier = 0.5
    elif total_tickets <= 3:
        violation_multiplier = 0.7
    else:
        violation_multiplier = 1.0
    
    severity_factor = severity_factor * violation_multiplier
    
    # Nighttime factor: percentage of violations at night (10pm-4am)
    nighttime_factor = (night_violations / total_tickets) if total_tickets > 0 else 0
    
    # Weighted crash risk score (removed cross-borough factor)
    crash_risk = (
        (severity_factor * 0.7) +
        (nighttime_factor * 0.3)
    ) * 100
    
    return round(min(crash_risk, 100), 1)


def get_crash_risk_level(crash_risk_score: float) -> dict:
    """
    Get crash risk level classification.
    
    Returns:
        Dict with level, color, and description
    """
    if crash_risk_score >= 75:
        return {"level": "HIGH", "color": "red", "description": "High fatality risk"}
    elif crash_risk_score >= 50:
        return {"level": "VERY_HIGH", "color": "orange", "description": "Very dangerous"}
    elif crash_risk_score >= 25:
        return {"level": "MODERATE", "color": "yellow", "description": "Concerning"}
    else:
        return {"level": "LOW", "color": "green", "description": "Low risk"}


# Enforcement lifecycle states
ENFORCEMENT_STATES = {
    "NEW": {"order": 1, "label": "New Case", "next_action": "Send Notice"},
    "NOTICE_SENT": {"order": 2, "label": "Notice Sent", "next_action": "Mark Follow-Up Due"},
    "FOLLOW_UP_DUE": {"order": 3, "label": "Follow-Up Due", "next_action": "Mark Compliant"},
    "COMPLIANT": {"order": 4, "label": "Compliant", "next_action": None},
    "ESCALATED": {"order": 5, "label": "Escalated", "next_action": None},
}


# NYC boroughs for jurisdiction determination
NYC_JURISDICTIONS = [
    'MANHATTAN', 'BROOKLYN', 'QUEENS', 'BRONX', 'STATEN ISLAND',
    'NEW YORK', 'KINGS', 'RICHMOND', 'NYC'
]


def get_jurisdiction_type(borough: str, court: str = None) -> str:
    """
    Determine if jurisdiction is NYC DOF or Local Court.
    """
    if borough:
        borough_upper = borough.upper().strip()
        for nyc in NYC_JURISDICTIONS:
            if nyc in borough_upper or borough_upper in nyc:
                return "NYC_DOF"
        if court and 'TVB' in court.upper():
            return "NYC_DOF"
    return "LOCAL_COURT"
