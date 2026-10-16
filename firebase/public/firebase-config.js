import { initializeApp } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-firestore.js";
const firebaseConfig = {

    apiKey:
        "AIzaSyBZG3E3WwyQU2yY4PLFBbH0HXBdQIoGgzE",

    authDomain:
        "quanlycuahang-afb59.firebaseapp.com",

    projectId:
        "quanlycuahang-afb59",

    storageBucket:
        "quanlycuahang-afb59.firebasestorage.app",

    messagingSenderId:
        "133124704288",

    appId:
        "1:133124704288:web:02c94fd8509e7ffd285445",

    measurementId:
        "G-NPJ593NFE3"

};
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
