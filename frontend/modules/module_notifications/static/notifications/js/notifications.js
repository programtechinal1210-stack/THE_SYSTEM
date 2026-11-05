document.addEventListener("DOMContentLoaded",function(){
    const bell=document.getElementById("notificationsBell");
    const dropdown=document.getElementById("notificationsDropdown");
    if(bell&&dropdown){
        bell.addEventListener("click",function(e){e.stopPropagation();dropdown.classList.toggle("hidden");});
        document.addEventListener("click",function(){dropdown.classList.add("hidden");});
        dropdown.addEventListener("click",function(e){e.stopPropagation();});
    }
});
function getCSRFToken(){return document.querySelector("[name=csrfmiddlewaretoken]")?.value||"";}
function showNotification(msg,type){const c={success:"bg-green-500",error:"bg-red-500",warning:"bg-yellow-500",info:"bg-blue-500"};const d=document.createElement("div");d.className=`fixed bottom-4 right-4 text-white px-4 py-2 rounded-lg z-50 ${c[type]||"bg-gray-500"}`;d.textContent=msg;document.body.appendChild(d);setTimeout(()=>{d.remove()},3000);}
