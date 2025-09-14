# Python-Picnic-API

The main purpose of this repository is to document changes I have developed until they are incorporated into the main branch of https://github.com/codesalatdev/python-picnic-api/

This library is not affiliated with Picnic and retrieves data from the endpoints of the mobile application. **Use at your own risk.**


## Summary of the new features 
```
import json
import sys
from python_picnic_api2 import PicnicAPI

p = PicnicAPI("XXXX","XXXXXX",'de');

print("\nSearch Results:")
searchResults = p.getRecipes("pizza")[0:5] # Limit to 5
print(json.dumps(searchResults, ensure_ascii=False, indent=2))

print("\nRecipe:")
details = p.getRecipeDetails("635b758a8004aa048d27193d")
print(json.dumps(details, ensure_ascii=False, indent=2))


print("\nArticle Details:")
d = p.get_article_details("s1028337")
print(json.dumps(d, indent=4))
```
