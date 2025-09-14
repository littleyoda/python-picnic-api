import re
from hashlib import md5
from urllib.parse import quote
import json
import jq
import typing_extensions
import urllib.parse


from .helper import (
    _extract_search_results,
    _tree_generator,
    _url_generator,
)
from .session import PicnicAPISession, PicnicAuthError

DEFAULT_URL = "https://storefront-prod.{}.picnicinternational.com/api/{}"
GLOBAL_GATEWAY_URL = "https://gateway-prod.global.picnicinternational.com"
DEFAULT_COUNTRY_CODE = "NL"
DEFAULT_API_VERSION = "15"
_HEADERS = {
    "x-picnic-agent": "30100;1.15.272-15295;",
    "x-picnic-did": "3C417201548B2E3B",
}


class PicnicAPI:
    def __init__(
        self,
        username: str = None,
        password: str = None,
        country_code: str = DEFAULT_COUNTRY_CODE,
        auth_token: str = None,
    ):
        self._country_code = country_code
        self._base_url = _url_generator(
            DEFAULT_URL, self._country_code, DEFAULT_API_VERSION
        )

        self.session = PicnicAPISession(auth_token=auth_token)

        # Login if not authenticated
        if not self.session.authenticated and username and password:
            self.login(username, password)

        self.high_level_categories = None

    def initialize_high_level_categories(self):
        """Initialize high-level categories once to avoid multiple requests."""
        if not self.high_level_categories:
            self.high_level_categories = self.get_categories(depth=1)

    def _get(self, path: str, add_picnic_headers=False):
        url = self._base_url + path

        # Make the request, add special picnic headers if needed
        headers = _HEADERS if add_picnic_headers else None
        response = self.session.get(url, headers=headers).json()

        if self._contains_auth_error(response):
            raise PicnicAuthError("Picnic authentication error")

        return response

    def _post(self, path: str, data=None, base_url_override=None):
        url = (base_url_override if base_url_override else self._base_url) + path
        response = self.session.post(url, json=data).json()

        if self._contains_auth_error(response):
            raise PicnicAuthError(
                f"Picnic authentication error: \
                    {response['error'].get('message')}"
            )

        return response

    @staticmethod
    def _contains_auth_error(response):
        if not isinstance(response, dict):
            return False

        error_code = response.setdefault("error", {}).get("code")
        return error_code == "AUTH_ERROR" or error_code == "AUTH_INVALID_CRED"

    def login(self, username: str, password: str):
        path = "/user/login"
        secret = md5(password.encode("utf-8")).hexdigest()
        data = {"key": username, "secret": secret, "client_id": 30100}

        return self._post(path, data)

    def logged_in(self):
        return self.session.authenticated

    def get_user(self):
        return self._get("/user")

    def search(self, term: str):
        path = f"/pages/search-page-results?search_term={quote(term)}"
        raw_results = self._get(path, add_picnic_headers=True)
        return _extract_search_results(raw_results)

    def get_cart(self):
        return self._get("/cart")

    def get_article(self, article_id: str, add_category_name=False):
        if add_category_name:
            raise NotImplementedError()
        path = f"/pages/product-details-page-root?id={article_id}"
        data = self._get(path, add_picnic_headers=True)
        article_details = []
        for block in data["body"]["child"]["child"]["children"]:
            if block["id"] == "product-details-page-root-main-container":
                article_details = block["pml"]["component"]["children"]

        if len(article_details) == 0:
            return None

        color_regex = re.compile(r"#\(#\d{6}\)")
        producer = re.sub(color_regex, "", str(article_details[1].get("markdown", "")))
        article_name = re.sub(color_regex, "", str(article_details[0]["markdown"]))

        article = {"name": f"{producer} {article_name}", "id": article_id}

        return article

    def get_article_category(self, article_id: str):
        path = "/articles/" + article_id + "/category"
        return self._get(path)

    def add_product(self, product_id: str, count: int = 1):
        data = {"product_id": product_id, "count": count}
        return self._post("/cart/add_product", data)

    def remove_product(self, product_id: str, count: int = 1):
        data = {"product_id": product_id, "count": count}
        return self._post("/cart/remove_product", data)

    def clear_cart(self):
        return self._post("/cart/clear")

    def get_delivery_slots(self):
        return self._get("/cart/delivery_slots")

    def get_delivery(self, delivery_id: str):
        path = "/deliveries/" + delivery_id
        return self._get(path)

    def get_delivery_scenario(self, delivery_id: str):
        path = "/deliveries/" + delivery_id + "/scenario"
        return self._get(path, add_picnic_headers=True)

    def get_delivery_position(self, delivery_id: str):
        path = "/deliveries/" + delivery_id + "/position"
        return self._get(path, add_picnic_headers=True)

    @typing_extensions.deprecated(
        """The option to show unsummarized deliveries was removed by picnic.
        The optional parameter 'summary' will be removed in the future and default
        to True.
        You can ignore this warning if you do not pass the 'summary' argument to
        this function."""
    )
    def get_deliveries(self, summary: bool = True, data: list = None):
        data = [] if data is None else data
        if not summary:
            raise NotImplementedError()
        return self._post("/deliveries/summary", data=data)

    def get_current_deliveries(self):
        return self.get_deliveries(data=["CURRENT"])

    def get_categories(self, depth: int = 0):
        return self._get(f"/my_store?depth={depth}")["catalog"]

    def print_categories(self, depth: int = 0):
        tree = "\n".join(_tree_generator(self.get_categories(depth=depth)))
        print(tree)

    def get_article_by_gtin(self, etan: str, maxRedirects: int = 5):
        # Finds the article ID for a gtin/ean (barcode).

        url = "https://picnic.app/" + self._country_code.lower() + "/qr/gtin/" + etan
        while maxRedirects > 0:
            if url == "http://picnic.app/nl/link/store/storefront":
                # gtin unknown
                return None
            r = self.session.get(url, headers=_HEADERS, allow_redirects=False)
            maxRedirects -= 1
            if ";id=" in r.url:
                # found the article id
                return self.get_article(r.url.split(";id=", 1)[1])
            if "Location" not in r.headers:
                # article id not found but also no futher redirect
                return None
            url = r.headers["Location"]
        return None
    
    JQ_EXTRACTION_FILTER = r'''
        # Extract accordion data
        def accordion_data:
          [
            .body.child.child.children[]? | 
            select(.id == "accordion-section")? | 
            .children[]? | 
            select(.id == "product-page-accordions")? | 
            .pml.component.items[]? | 
            (.header.child.children[]? | select(.type == "ICON" and has("iconKey"))? | .iconKey) as $icon |
            if $icon == "apple" then
              {
                iconKey: $icon,
                markdowns: [.body.child.children[]? | select(.type == "STACK") | 
                            [.children[]? | select(.type == "RICH_TEXT" and has("markdown")) | .markdown] | 
                            select(length > 0)]
              }
            else
              {
                iconKey: $icon,
                markdowns: [.body | .. | objects | select(.type == "RICH_TEXT" and has("markdown")) | .markdown]
              }
            end |
            select(.iconKey and (.markdowns | length > 0))
          ] | 
          map({(.iconKey): .markdowns}) | 
          add // {};
        
        # Extract name data from main container
        def name_data:
          (.. | objects | select(.id == "product-details-page-root-main-container") | 
           .pml.component.children) as $children |
          
          if ($children | length) > 0 then
            # First child is always the product name (RICH_TEXT with HEADER1)
            ($children[0] | select(.type == "RICH_TEXT" and .textType == "HEADER1") | .markdown | gsub("#\\(#[0-9a-fA-F]+\\)"; "")) as $name |
            
            # Check if second child is manufacturer (RICH_TEXT with textAttributes, no textType) or skip if STACK
            (if ($children | length) > 1 and ($children[1].type == "RICH_TEXT") and (($children[1].textType // null) == null) and ($children[1] | has("textAttributes")) 
             then ($children[1].markdown) 
             else null end) as $manufacturer |
            
            # Find weight in STACK children
            ($children[] | select(.type == "STACK") | .children[]? | select(.type == "RICH_TEXT" and has("markdown")) | .markdown | gsub("#\\(#[0-9a-fA-F]+\\)"; "")) as $weight |
            
            {
              product: ($name // null),
              manufacturer: ($manufacturer // null),  
              quantity: ($weight // null),
              name: (if ($manufacturer // null) != null then ($manufacturer + " " + ($name // "")) else ($name // null) end)
            }
          else {} end;
        
        # Extract image IDs from main image container
        def image_data:
          (.. | objects | select(.id == "product-page-image-gallery-main-image-container") | 
           [.. | objects | select(.type == "IMAGE" and has("source")) | .source.id]) as $image_ids |
          if ($image_ids | length) > 0 then {image_ids: $image_ids} else {} end;
        
        # Extract selling_unit_id from analytics
        def selling_unit_data:
          ([.. | objects | select(has("analytics")) | .analytics.contexts[]? | select(has("data")) | .data | select(has("selling_unit_id")) | .selling_unit_id] | unique) as $selling_unit_ids |
          if ($selling_unit_ids | length) > 0 then {selling_unit_id: ($selling_unit_ids[0] // null)} else {} end;
        
        # Extract product description (optional) 
        def description_data:
          ([.. | objects | select(.id == "product-page-description") | .. | objects | select(.type == "RICH_TEXT" and has("markdown")) | .markdown]) as $description_markdowns |
          {"product-description": $description_markdowns};
        
        # Extract categories from target URLs
        def category_data:
          ([.. | objects | select(has("target")) | .target | select(test("app\\.picnic://categories/")) | capture("app\\.picnic://categories/(?<l1>[0-9]+)(/l2/(?<l2>[0-9]+))?(/l3/(?<l3>[0-9]+))?") | [.l1, .l2, .l3] | map(select(. != null)) | map(tonumber)] | unique) as $categories |
          if ($categories | length) > 0 then {"categories": ($categories[0] // [])} else {} end;
        
        # Extract allergies from product-page-allergies
        def allergies_data:
          ([.. | objects | select(.id == "product-page-allergies") | .. | objects | select(.type == "RICH_TEXT" and has("markdown")) | .markdown] | unique) as $allergies |
          if ($allergies | length) > 0 then {"allergies": $allergies} else {} end;
        
        # Rename keys after extraction
        (accordion_data // {}) + (name_data // {}) + (image_data // {}) + (selling_unit_data // {}) + (description_data // {}) + (category_data // {}) + (allergies_data // {}) |
        with_entries(
          if .key == "whisk" then .key = "preparation"
          elif .key == "apple" then .key = "nutritional_values"
          elif .key == "list" then .key = "ingredients"  
          elif .key == "infoCircle" then .key = "info"
          else .
          end
        )
    '''
    
    def get_article_details(self, article_id):
        path = f"/pages/product-details-page-root?id={article_id}&show_category_action=true"
        data = self._get(path, add_picnic_headers=True)
    
        # Use jq to extract accordion data
        compiled_filter = jq.compile(self.JQ_EXTRACTION_FILTER)
        
        # Handle StopIteration for queries that return no results
        try:
            result = compiled_filter.input(data).first()
        except StopIteration:
            return None
        
        if not result or not isinstance(result, dict) or not result:
            return None
        return result


    def getRecipes(self, searchTerm):
        searchTerm = urllib.parse.quote_plus(searchTerm)
        recipes = self._get(f"/pages/search-page-results?search_term={searchTerm}&page_context=MEALS&is_recipe=true", add_picnic_headers=True)
    
        query = (
                # Search in the recipes search results
                '.. | objects | select(.id=="search-flat-recipes-result") | .children[] | {'
                # Recipe Name
                ' name: .pml.component.accessibilityLabel, '
                # Return first recipe_id
                'recipe_id: ([ .. | objects | .recipe_id? ] | map(select(. != null)) | .[0]), '
                # Return first image_id
                'image_id: ([ .. | objects | select(.type=="IMAGE") | .source.id? ] | map(select(. != null)) | .[0])'
                '}'
            )
        
        compiled = jq.compile(query)
        return compiled.input(recipes).all()

    def getRecipeDetails(self, recipe_id):
        data = self._get(f"/pages/recipe-details-page?recipe_id={recipe_id}", add_picnic_headers=True)
     
        extraction = {
            "ingredients":(
                ".. | objects | select(.id==\"recipe-core-ingredients-details-section\")"
                " | .. | objects | .markdown? | select(type == \"string\")"
                ),
            "utensils":(
                ".. | objects | select(.id==\"recipe-ingredients-utensils\")"
                " | .. | objects | .markdown? | select(type == \"string\")"
            ),
            "instructions": (
                ".. | objects | select(.id==\"recipe-details-instructions-section\")"
                " | .. | objects | .markdown? | select(type == \"string\")"
            ),
            "description": (
                ".. | objects | select(.id==\"recipe-description-section\")"
                " | .. | objects | .markdown? | select(type == \"string\")"
            ),
            "articles": (
                ".. | objects | select(.id==\"recipe-portioning-content-wrapper\")"
                " | .. | objects | .ingredientsState? | select(. != null) | .[]"
            ),        
            "name": (
                ".. | objects | select(.type==\"RICH_TEXT\" and .textType==\"HEADLINE1\")"
                " | .markdown? | select(type == \"string\")"
            ),
            "url": (
                ".. | strings | select(test(\"https://picnic[.]app/de/go/[A-Za-z0-9]+\"))"
                " | match(\"https://picnic[.]app/de/go/[A-Za-z0-9]+\").string"
            )
        }
    
        out = {}
        for desc, expression in extraction.items():
            compiled = jq.compile(expression)
            out[desc] = compiled.input(data).all() 
        return out


__all__ = ["PicnicAPI"]
