

import { auth, db } from "./firebase-config.js";
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";
import { doc, getDoc, collection, getDocs, writeBatch, serverTimestamp, query, where, setDoc } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-firestore.js";
const input = document.getElementById("excelFile");
const logout = document.getElementById("logoutButton");
const status = document.createElement("p");
status.setAttribute("role", "status");
status.style.marginBottom = "16px";
document.querySelector(".table-wrapper").before(status);
let currentUid = null;
let selectedStoreId = null;
let stores = [];
let loading = false;
let selectionVersion = 0;
const select = document.getElementById("storeSelect");
function lockControls(locked){input.disabled=locked;select.disabled=locked;document.getElementById("createStoreButton").disabled=locked;logout.disabled=busy;}

let busy = false;
input.disabled = true;

function message(text, error = false) {
    status.textContent = text;
    status.style.color = error ? "#dc2626" : "#2563eb";
}
function showError(error) {
    console.error(error);
    const hint = error.code === "permission-denied"
        ? " Kiểm tra và Publish Firestore Rules đã gửi kèm."
        : " Kiểm tra kết nối mạng và mục Console (F12).";
    message("Không thể hoàn tất: " + (error.message || error) + hint, true);
}
function productsRef(storeId) {
    return collection(db, "stores", storeId, "products");
}
function displayProducts(products) {
    const tbody = document.getElementById("productTableBody");
    tbody.replaceChildren();
    products.forEach((product, index) => {
        const row = document.createElement("tr");
        [index + 1, product.name, product.barcode || "Chưa có barcode", product.importDate, product.shelfLife, product.price].forEach(value => {
            const cell = document.createElement("td");
            cell.textContent = value ?? "";
            row.appendChild(cell);
        });
        tbody.appendChild(row);
    });
    if (!products.length) {
        const row = tbody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 6;
        cell.textContent = "Chưa có sản phẩm";
        cell.style.textAlign = "center";
    }
    document.getElementById("productCount").textContent = products.length;
}
async function loadStores(uid) {
    const owned = await getDocs(query(collection(db,"stores"),where("ownerUid","==",uid)));
    const map = new Map(owned.docs.map(d=>[d.id,{...d.data(),id:d.id}]));
    // Hồ sơ cũ có Document ID bằng UID: bổ sung ownerUid, giữ sản phẩm.
    const legacyRef = doc(db,"stores",uid);
    const legacy = await getDoc(legacyRef);
    if(legacy.exists()) {
        const data=legacy.data();
        if(data.ownerUid===uid || (!data.ownerUid && data.uid===uid)) {
            if(!data.ownerUid) await setDoc(legacyRef,{ownerUid:uid},{merge:true});
            map.set(uid,{...data,ownerUid:uid,id:uid});
        }
    }
    if(auth.currentUser?.uid!==uid)return;
    stores=[...map.values()].sort((a,b)=>(a.storeName||"").localeCompare(b.storeName||"","vi"));
    select.replaceChildren();
    for(const store of stores){const option=document.createElement("option");option.value=store.id;option.textContent=store.storeName||store.id;select.appendChild(option);}
    if(!stores.length){const option=document.createElement("option");option.value="";option.textContent="Chưa có cửa hàng";select.appendChild(option);document.getElementById("createStorePanel").open=true;}
    await chooseStore(stores.some(s=>s.id===selectedStoreId)?selectedStoreId:stores[0]?.id);
}
async function chooseStore(id){
    const version=++selectionVersion;
    loading=true;lockControls(true);selectedStoreId=id||null;
    const store=stores.find(s=>s.id===id);
    displayProducts([]);
    for(const [element,value] of Object.entries({storeNameDisplay:store?.storeName,storeId:store?.storeId||store?.id,rfidId:store?.rfidId,wifiName:store?.wifiSSID})) document.getElementById(element).textContent=value||"Chưa có";
    try{
        if(!store){message("Chưa có cửa hàng. Điền biểu mẫu Thêm cửa hàng để bắt đầu.");return;}
        select.value=id;message("Đang tải sản phẩm...");
        const saved=await getDocs(productsRef(id));
        if(version!==selectionVersion)return;
        displayProducts(saved.docs.map(d=>d.data()).sort((a,b)=>a.rowIndex-b.rowIndex));
        message("Đã tải "+saved.size+" sản phẩm của "+store.storeName+".");
    }catch(error){selectedStoreId=null;showError(error);}
    finally{if(version===selectionVersion){loading=false;lockControls(false);input.disabled=!selectedStoreId;select.disabled=!stores.length;}}
}
select.addEventListener("change",()=>{if(!busy&&!loading)chooseStore(select.value);});
onAuthStateChanged(auth,async user=>{
    currentUid=null;selectedStoreId=null;lockControls(true);
    if(!user){window.location.href="index.html";return;}
    document.getElementById("accountEmail").textContent="Tài khoản: "+user.email;
    message("Đang tải cửa hàng...");
    try{currentUid=user.uid;await loadStores(user.uid);}
    catch(error){showError(error);document.getElementById("createStoreButton").disabled=false;logout.disabled=false;}
});
document.getElementById("createStoreForm").addEventListener("submit",async event=>{
    event.preventDefault();if(busy||loading||!auth.currentUser)return;
    busy=true;lockControls(true);
    const uid=auth.currentUser.uid;
    let created=false;
    try{
        const data=new FormData(event.currentTarget);
        const storeName=String(data.get("storeName")).trim();
        const rawRfid=String(data.get("rfidId")).trim().replace(/[\s:-]/g, "").toUpperCase();
        if(!/^(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})$/.test(rawRfid))
            throw new Error("UID RFID phải gồm 4, 7 hoặc 10 byte hex, ví dụ CD 4B 1E 03; không nhập email.");
        const rfidId=rawRfid.match(/.{2}/g).join(" ");
        const duplicate=await getDocs(query(collection(db,"stores"),where("ownerUid","==",uid),where("rfidId","==",rfidId)));
        if(!duplicate.empty)throw new Error("Tài khoản này đã có cửa hàng gắn với thẻ RFID này.");
        const wifiSSID=String(data.get("wifiSSID"));
        const wifiPassword=String(data.get("wifiPassword"));
        if(!storeName||!rfidId||!wifiSSID.trim())throw new Error("Điền tên cửa hàng, RFID và Wi-Fi.");
        const ref=doc(collection(db,"stores"));
        message("Đang lưu cửa hàng...");
        await setDoc(ref,{ownerUid:uid,storeId:ref.id,storeName,rfidId,wifiSSID,wifiPassword,email:auth.currentUser.email,createdAt:serverTimestamp()});
        created=true;selectedStoreId=ref.id;event.target.reset();
        await loadStores(uid);
        message("Đã tạo cửa hàng. Bạn có thể upload Excel.");
    }catch(error){showError(error);if(created)message("Cửa hàng đã lưu nhưng chưa tải lại được. Hãy tải lại trang.",true);}
    finally{busy=false;lockControls(false);input.disabled=!selectedStoreId;select.disabled=!stores.length;}
});

function readProducts(workbook) {
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    if (!sheet) throw new Error("File không có sheet dữ liệu.");
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: "", raw: false });
    if (!rows.length) throw new Error("File Excel không có dữ liệu.");
    const aliases = {
        name: ["Tên sản phẩm"],
        barcode: ["Barcode", "Mã vạch", "Mã barcode"],
        importDate: ["Ngày nhập", "Ngày nhập hàng"],
        shelfLife: ["Thời gian sử dụng"],
        price: ["Giá bán", "Giá", "Giá cả"]
    };
    return rows.map((row, index) => {
        const normalized = Object.fromEntries(Object.entries(row).map(([k,v]) => [k.trim().toLocaleLowerCase("vi"), v]));
        const product = { rowIndex: index };
        for (const [field, names] of Object.entries(aliases)) {
            const key = names.map(n => n.toLocaleLowerCase("vi")).find(n => Object.hasOwn(normalized, n));
            if (!key) throw new Error("Thiếu cột " + names[0] + ". Kiểm tra hàng tiêu đề của Excel.");
            const value = String(normalized[key]).trim();
            if (!value) throw new Error("Sản phẩm thứ " + (index + 1) + " thiếu " + names[0] + ".");
            if (value.length > 1000) throw new Error("Ô dữ liệu quá dài ở sản phẩm thứ " + (index + 1));
            product[field] = value;
        }
        return product;
    });
}
input.addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file || busy) return;
    if (!currentUid || !selectedStoreId || loading || auth.currentUser?.uid !== currentUid) {
        message("Hãy chờ tải xong thông tin cửa hàng rồi upload.", true);
        input.value = "";
        return;
    }
    const uid = currentUid;
    const storeId = selectedStoreId;
    busy = true;
    lockControls(true);
    try {
        if (file.size > 5 * 1024 * 1024) throw new Error("Vui lòng dùng file dưới 5 MB.");
        message("Đang đọc và kiểm tra Excel...");
        const workbook = XLSX.read(await file.arrayBuffer(), { type: "array" });
        const products = readProducts(workbook);
        const previous = await getDocs(productsRef(storeId));
        // Một batch thay thế toàn bộ danh sách, tránh lưu dở dang.
        if (previous.size + products.length > 450) {
            throw new Error("Bản này hỗ trợ tối đa 450 thao tác mỗi lần: số sản phẩm cũ + số sản phẩm mới phải ≤ 450. Dữ liệu cũ vẫn được giữ nguyên.");
        }
        if (previous.size && !window.confirm("File mới sẽ thay thế toàn bộ " + previous.size + " sản phẩm đã lưu bằng " + products.length + " sản phẩm. Tiếp tục?")) {
            message("Đã hủy. Danh sách cũ vẫn được giữ nguyên.");
            return;
        }
        if (auth.currentUser?.uid !== uid) throw new Error("Phiên đăng nhập đã thay đổi. Vui lòng đăng nhập lại.");
        message("Đang lưu lên Firestore... Hãy chờ thông báo thành công.");
        const batch = writeBatch(db);
        previous.docs.forEach(d => batch.delete(d.ref));
        products.forEach(product => batch.set(doc(productsRef(storeId)), { ...product, createdAt: serverTimestamp() }));
        await batch.commit();
        displayProducts(products);
        message("Đã lưu " + products.length + " sản phẩm lên Firestore. Bạn có thể tải lại trang hoặc đăng nhập lại.");
    } catch (error) { showError(error); }
    finally {
        busy = false;
        input.value = "";
        lockControls(false);
        input.disabled = !selectedStoreId;
        select.disabled = !stores.length;
    }
});
logout.addEventListener("click", async () => {
    if (busy) return;
    try { await signOut(auth); }
    catch (error) { showError(error); }
});

