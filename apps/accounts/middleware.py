from django.conf import settings

class DisableBrowserCacheMiddleware:
    """
    Prevents the browser from caching pages.
    This ensures that when a user clicks "Back" after logging out, 
    they don't see the old authenticated page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add headers to prevent caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response