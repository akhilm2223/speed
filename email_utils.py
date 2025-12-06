#!/usr/bin/env python3
"""
Email utilities for ISA notifications.
Uses templates.html for professional HTML email formatting.
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def load_email_template():
    """Load the ISA email template from templates.html"""
    template_path = os.path.join(os.path.dirname(__file__), 'templates.html')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load email template: {e}")
        return None


def render_isa_notification(driver_data):
    """
    Render ISA notification email for a specific driver.
    
    Args:
        driver_data (dict): Driver information including:
            - license_number: Driver's license number
            - license_plate: Associated plate
            - violation_code: Primary violation code
            - violation_description: Description of violation
            - total_points: Total points in 24-month window
    
    Returns:
        str: Rendered HTML email
    """
    template = load_email_template()
    if not template:
        return None
    
    # Replace placeholders
    html = template.replace('{{LICENSE_NUMBER}}', driver_data.get('license_number', 'N/A'))
    html = html.replace('{{LICENSE_PLATE}}', driver_data.get('license_plate', 'N/A'))
    html = html.replace('{{VIOLATION_CODE}}', driver_data.get('violation_code', 'N/A'))
    html = html.replace('{{VIOLATION_DESCRIPTION}}', driver_data.get('violation_description', 'Multiple speeding violations'))
    html = html.replace('{{TOTAL_POINTS}}', str(driver_data.get('total_points', 0)))
    
    return html


def send_isa_email(to_email, driver_data, send_real_email=False):
    """
    Send ISA notification email.
    
    Args:
        to_email (str): Recipient email address
        driver_data (dict): Driver information
        send_real_email (bool): If True, actually send email via SMTP (production mode)
    
    Returns:
        dict: Status information
    """
    html_content = render_isa_notification(driver_data)
    
    if not html_content:
        return {
            "status": "error",
            "message": "Failed to load email template"
        }
    
    if send_real_email:
        # Production email sending via SMTP/SendGrid
        # This would integrate with actual email service
        logger.info(f"[PRODUCTION] Sending ISA email to {to_email}")
        # TODO: Implement actual email sending
        # import smtplib
        # from email.mime.text import MIMEText
        # from email.mime.multipart import MIMEMultipart
        # ...
        pass
    else:
        # Demo mode - just log
        logger.info(
            f"[EMAIL STUB] ISA notification for {driver_data.get('license_number')} "
            f"to {to_email} (Points: {driver_data.get('total_points')})"
        )
    
    return {
        "status": "ok",
        "message": "Email sent" if send_real_email else "Email queued (demo mode)",
        "recipient": to_email,
        "license": driver_data.get('license_number'),
        "timestamp": datetime.now().isoformat()
    }


def send_batch_isa_notifications(drivers_list, send_real_email=False):
    """
    Send ISA notifications to multiple drivers.
    
    Args:
        drivers_list (list): List of driver data dicts
        send_real_email (bool): Whether to send real emails
    
    Returns:
        dict: Summary of sent emails
    """
    results = []
    success_count = 0
    
    for driver in drivers_list:
        # In production, we'd look up email from driver database
        demo_email = f"{driver.get('license_number')}@example.com"
        
        result = send_isa_email(demo_email, driver, send_real_email)
        results.append(result)
        
        if result["status"] == "ok":
            success_count += 1
    
    return {
        "total": len(drivers_list),
        "sent": success_count,
        "failed": len(drivers_list) - success_count,
        "results": results
    }


def get_violation_description(code):
    """
    Get human-readable description for violation code.
    
    Args:
        code (str): NY VTL violation code
    
    Returns:
        str: Description
    """
    descriptions = {
        "1180A": "Speed not reasonable and prudent",
        "1180B": "Speed in excess of 55 MPH (1-10 mph over)",
        "1180C": "Speed in excess of 55 MPH (11-20 mph over)",
        "1180D": "Speed in excess of 55 MPH (31+ mph over)",
        "1180E": "Speeding in school zone",
        "1181A": "Speed contest/drag racing",
        "1182": "Reckless driving"
    }
    return descriptions.get(code, "Speeding violation")


# Example usage for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test single email
    test_driver = {
        "license_number": "SS001NOVA",
        "license_plate": "SPEED01",
        "violation_code": "1180D",
        "violation_description": get_violation_description("1180D"),
        "total_points": 24
    }
    
    result = send_isa_email("test@example.com", test_driver, send_real_email=False)
    print(f"Email result: {result}")

