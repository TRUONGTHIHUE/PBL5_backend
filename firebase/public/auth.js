import { auth } from "./firebase-config.js";
import { signInWithEmailAndPassword, createUserWithEmailAndPassword, sendPasswordResetEmail } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";
const $ = id => document.getElementById(id);
function show(text,error=false){$("message").textContent=text;$("message").style.color=error?"#dc2626":"#2563eb";}
async function submit(form,operation){const button=form.querySelector("button");button.disabled=true;try{await operation();}catch(e){console.error(e);show(e.code+": "+e.message,true);}finally{button.disabled=false;}}
$("loginForm").addEventListener("submit",e=>{e.preventDefault();submit(e.currentTarget,async()=>{await signInWithEmailAndPassword(auth,$("loginEmail").value.trim(),$("loginPassword").value);window.location.href="product.html";});});
$("registerForm").addEventListener("submit",e=>{e.preventDefault();submit(e.currentTarget,async()=>{if($("registerPassword").value!==$("confirmPassword").value)throw new Error("Hai mật khẩu chưa khớp.");await createUserWithEmailAndPassword(auth,$("registerEmail").value.trim(),$("registerPassword").value);window.location.href="product.html";});});
$("resetPassword").addEventListener("click",async()=>{const email=$("loginEmail").value.trim();if(!email){show("Nhập email vào ô đăng nhập trước.",true);return;}$("resetPassword").disabled=true;try{await sendPasswordResetEmail(auth,email);show("Đã gửi yêu cầu đặt lại mật khẩu. Kiểm tra email và thư rác.");}catch(e){show(e.message,true);}finally{$("resetPassword").disabled=false;}});
