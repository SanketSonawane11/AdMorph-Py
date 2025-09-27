import requests
import json

BACKEND_URL = "http://localhost:8000"

enhanced_campaigns = [
    {
        "campaign_id": "tech_gear_01",
        "original_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #ddd; background-color:#f5f5f5; text-align:center; font-family:sans-serif; transition:all 0.5s ease-in-out; height:250px; width:350px; overflow:hidden;'><h3>🎧 Experience Crystal Clear Sound</h3><p style='font-size:0.9em; margin:10px 0;'>Elevate your music with our new noise-cancelling headphones.</p><img src='https://via.placeholder.com/200x120.png?text=Headphones' style='width:100%; height:auto; border-radius:8px; margin-bottom:10px;'/><button style='padding:10px 20px; border-radius:20px; border:none; background-color:#007bff; color:white; cursor:pointer;'>Shop Now</button></div>",
        "v1_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #f00; background-color:#ffe6e6; text-align:center; font-family:sans-serif; opacity:0.8; height:250px; width:350px; overflow:hidden;'><h4>Don't miss the article.</h4><p style='font-size:0.8em;'>Scroll on if you're not interested.</p></div>",
        "v2_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #ffa500; background-color:#fff2e6; text-align:center; font-family:sans-serif; animation:pulse 1.5s infinite; overflow:hidden; height:250px; width:350px;'><h4>⏳ Limited Time Offer</h4><p style='font-size:0.9em; margin:10px 0;'>Get <b>50% off</b> these headphones now!</p><button style='padding:12px 25px; border-radius:25px; border:none; background-color:#ff9800; color:white; font-weight:bold; cursor:pointer;'>Claim Discount</button></div>",
        "v3_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #0a0; background-color:#e6ffe6; text-align:center; font-family:sans-serif; animation:fadeIn 1s; overflow:hidden; height:250px; width:350px;'><h4 style='color:#006400;'>🔥 Hot Deal!</h4><p style='font-size:0.9em; margin:10px 0;'>Users are loving the sound quality. Join them now!</p><button style='padding:15px 30px; border-radius:30px; border:none; background-color:#28a745; color:white; font-weight:bold; cursor:pointer; animation:jiggle 0.5s infinite;'>Buy It Today</button></div>"
    },
    {
        "campaign_id": "health_supplements_02",
        "original_html": "<div style='box-sizing:border-box; padding:15px; border:2px solid #6c757d; background-color:#f8f9fa; text-align:center; font-family:sans-serif; overflow:hidden; height:250px; width:350px;'><h3 style='color:#007bff;'>Boost Your Day</h3><p style='font-size:0.85em;'>Get the vitamins you need with our daily supplement.</p><img src='https://via.placeholder.com/180x100.png?text=Supplement+Bottle' style='width:100%; height:auto; margin:10px 0; border-radius:8px;'/></div>",
        "v1_html": "<div style='box-sizing:border-box; padding:15px; border:2px solid #adb5bd; background-color:#e9ecef; text-align:center; font-family:sans-serif; opacity:0.7; height:250px; width:350px; overflow:hidden;'><h4>Your health, your choice.</h4><p style='font-size:0.8em;'>This ad is just for informational purposes.</p></div>",
        "v2_html": "<div style='box-sizing:border-box; padding:15px; border:2px solid #ffc107; background-color:#fff3cd; text-align:center; font-family:sans-serif; animation:slideIn 1s; overflow:hidden; height:250px; width:350px;'><h4>Curious?</h4><p style='font-size:0.85em; margin:10px 0;'>Find out why our customers love this supplement.</p><a href='#' style='display:inline-block; padding:8px 15px; border-radius:5px; background-color:#ffc107; color:black; text-decoration:none;'>Read Reviews</a></div>",
        "v3_html": "<div style='box-sizing:border-box; padding:15px; border:2px solid #28a745; background-color:#d4edda; text-align:center; font-family:sans-serif; animation:bounceIn 1s; overflow:hidden; height:250px; width:350px;'><h4>Ready to feel better?</h4><p style='font-size:0.9em; margin:10px 0;'>One click away from a healthier you.</p><a href='#' style='display:inline-block; padding:10px 20px; border-radius:5px; background-color:#28a745; color:white; text-decoration:none;'>Order Now</a></div>"
    },
    {
        "campaign_id": "travel_agency_03",
        "original_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #0056b3; background:linear-gradient(135deg, #007bff, #0056b3); color:white; text-align:center; font-family:sans-serif; overflow:hidden; height:250px; width:350px;'><h3>✈️ Your Next Adventure Awaits</h3><p style='font-size:0.9em; margin:10px 0;'>Explore our curated travel packages to paradise destinations.</p><img src='https://via.placeholder.com/220x150.png?text=Travel+Photo' style='width:100%; height:auto; border-radius:10px; margin-bottom:10px;'/></div>",
        "v1_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #495057; background-color:#343a40; color:#f8f9fa; text-align:center; font-family:sans-serif; opacity:0.9; height:250px; width:350px; overflow:hidden;'><h4>Dreaming of an escape?</h4><p style='font-size:0.8em;'>Maybe later. No pressure.</p></div>",
        "v2_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #6f42c1; background-color:#e6e6fa; text-align:center; font-family:sans-serif; animation:float 2s infinite; overflow:hidden; height:250px; width:350px;'><h4>Hesitant?</h4><p style='font-size:0.9em; margin:10px 0;'>Unlock a special deal on your dream trip today.</p><a href='#' style='display:inline-block; padding:10px 20px; border-radius:5px; background-color:#6f42c1; color:white; text-decoration:none;'>Get a Quote</a></div>",
        "v3_html": "<div style='box-sizing:border-box; padding:20px; border:2px solid #ffc107; background-color:#fff8e1; text-align:center; font-family:sans-serif; animation:pulse 1.5s infinite; height:250px; width:350px; overflow:hidden;'><h4>Ready to pack?</h4><p style='font-size:0.9em; margin:10px 0;'>Book your flight and hotel in one click!</p><a href='#' style='display:inline-block; padding:12px 25px; border-radius:5px; background-color:#ffc107; color:black; text-decoration:none; font-weight:bold;'>Book Now</a></div>"
    }
]

def seed_campaigns():
    """Sends each campaign to the FastAPI endpoint to be seeded."""
    print("Starting campaign seeding process...\n")
    
    success_count = 0
    total_count = len(enhanced_campaigns)
    
    for i, ad in enumerate(enhanced_campaigns, 1):
        try:
            print(f"[{i}/{total_count}] Seeding campaign: {ad['campaign_id']}...")
            response = requests.post(
                f"{BACKEND_URL}/admin/register_campaign",
                json=ad,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()  
            print(f"Successfully seeded {ad['campaign_id']}")
            success_count += 1
        except requests.exceptions.ConnectionError:
            print(f"Connection failed for {ad['campaign_id']}: Make sure your FastAPI server is running on {BACKEND_URL}")
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error for {ad['campaign_id']}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to seed {ad['campaign_id']}: {e}")
        
        print() 
    
    print(f"📊 Seeding Summary:")
    print(f"Success: {success_count}/{total_count}")
    print(f"Failed: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print("\nAll campaigns seeded successfully!")
    elif success_count > 0:
        print(f"\nPartial success: {success_count} campaigns seeded")
    else:
        print("\nSeeding failed completely. Check your server connection.")

if __name__ == "__main__":
    seed_campaigns()