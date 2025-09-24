import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email
from django.utils.translation import gettext_lazy as _


# Common domain typos mapping - just the most frequent ones
COMMON_TYPOS = {
    'gmial.com': 'gmail.com',
    'gmai.com': 'gmail.com', 
    'gmail.co': 'gmail.com',
    'gmail.con': 'gmail.com',
    'yahooo.com': 'yahoo.com',
    'yahoo.co': 'yahoo.com',
    'hotmial.com': 'hotmail.com',
    'hotmail.co': 'hotmail.com',
    'outlok.com': 'outlook.com',
    'outlook.co': 'outlook.com',
}

# Disposable email domains to block
DISPOSABLE_DOMAINS = {
    '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
    'mailinator.com', 'temp-mail.org', 'throwaway.email',
    'yopmail.com', 'maildrop.cc', 'tempmail.plus',
    'discard.email', '0-mail.com', '33mail.com',
    'fakemailgenerator.com', 'temporaryemail.us', 'emailondeck.com'
}


def validate_email_with_suggestions(email):
    """
    Enhanced email validation that:
    1. Does basic Django email validation
    2. Checks for common typos and suggests corrections
    3. Blocks disposable email domains
    """
    if not email:
        raise ValidationError(_('Email address is required.'))
    
    email = email.strip().lower()
    
    # Basic Django validation first
    try:
        django_validate_email(email)
    except ValidationError:
        raise ValidationError(_('Enter a valid email address.'))
    
    # Check for typos
    if '@' in email:
        domain = email.split('@')[1]
        if domain in COMMON_TYPOS:
            local_part = email.split('@')[0]
            suggested_email = f"{local_part}@{COMMON_TYPOS[domain]}"
            raise ValidationError(
                _('Did you mean "{suggestion}"? Please check your email address.').format(
                    suggestion=suggested_email
                )
            )
    
    # Check for disposable domains
    if '@' in email:
        domain = email.split('@')[1]
        if domain in DISPOSABLE_DOMAINS:
            raise ValidationError(
                _('Disposable email addresses are not allowed. Please use a permanent email address.')
            )
    
    return email


def validate_no_disposable_email(email):
    """Simple validator to just block disposable emails."""
    if not email or '@' not in email:
        return email
    
    domain = email.split('@')[1].lower()
    if domain in DISPOSABLE_DOMAINS:
        raise ValidationError(
            _('Disposable email addresses are not allowed. Please use a permanent email address.')
        )
    
    return email