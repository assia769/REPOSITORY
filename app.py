from flask import Flask, render_template, request, url_for, redirect, flash
from flask_mysqldb import MySQL
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = 'many random bytes'

# Configuration de la base de données
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'assia2004'
app.config['MYSQL_DB'] = 'bibliotheque'

mysql = MySQL(app)

# Page d'accueil
@app.route('/')
def index():
    return render_template('index.html')

# Gestion des documents
@app.route('/documents')
def list_documents():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT d.reference, d.titre, d.annee_publication, d.editeur, d.type_document, 
               COUNT(e.id_exemplaire) as nombre_exemplaires,
               SUM(CASE WHEN e.statut = 'en rayon' THEN 1 ELSE 0 END) as disponibles
        FROM documents d
        LEFT JOIN exemplaires e ON d.reference = e.reference_document
        GROUP BY d.reference
    """)
    documents = cur.fetchall()
    cur.close()
    return render_template('documents.html', documents=documents)

@app.route('/documents/ajouter', methods=['GET', 'POST'])
def ajouter_document():
    if request.method == 'POST':
        titre = request.form['titre']
        annee_publication = request.form['annee_publication']
        editeur = request.form['editeur']
        type_document = request.form['type_document']
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO documents (titre, annee_publication, editeur, type_document) 
            VALUES (%s, %s, %s, %s)
        """, (titre, annee_publication, editeur, type_document))
        
        if type_document == 'livre':
            auteurs = request.form['auteurs']
            ISBN = request.form['ISBN']
            reference = cur.lastrowid
            cur.execute("""
                INSERT INTO livres (reference, auteurs, ISBN) 
                VALUES (%s, %s, %s)
            """, (reference, auteurs, ISBN))
        
        mysql.connection.commit()
        cur.close()
        flash('Document ajouté avec succès')
        return redirect(url_for('list_documents'))
    
    return render_template('ajouter_document.html')

# Gestion des exemplaires
@app.route('/exemplaires/<int:reference>')
def list_exemplaires(reference):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT * FROM exemplaires 
        WHERE reference_document = %s
    """, (reference,))
    exemplaires = cur.fetchall()
    cur.close()
    return render_template('exemplaires.html', exemplaires=exemplaires, reference=reference)

@app.route('/exemplaires/ajouter/<int:reference>', methods=['GET', 'POST'])
def ajouter_exemplaire(reference):
    if request.method == 'POST':
        date_achat = request.form['date_achat']
        etat = request.form['etat']
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO exemplaires (reference_document, date_achat, etat) 
            VALUES (%s, %s, %s)
        """, (reference, date_achat, etat))
        
        mysql.connection.commit()
        cur.close()
        flash('Exemplaire ajouté avec succès')
        return redirect(url_for('list_exemplaires', reference=reference))
    
    return render_template('ajouter_exemplaire.html', reference=reference)

# Gestion des emprunts
@app.route('/emprunts')
def list_emprunts():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT e.id_emprunt, u.nom, d.titre, e.date_debut, e.date_fin, e.statut
        FROM emprunts e
        JOIN utilisateurs u ON e.id_utilisateur = u.id_utilisateur
        JOIN exemplaires ex ON e.id_exemplaire = ex.id_exemplaire
        JOIN documents d ON ex.reference_document = d.reference
    """)
    emprunts = cur.fetchall()
    cur.close()
    return render_template('emprunts.html', emprunts=emprunts)

@app.route('/emprunts/ajouter', methods=['GET', 'POST'])
def ajouter_emprunt():
    if request.method == 'POST':
        id_utilisateur = request.form['id_utilisateur']
        id_exemplaire = request.form['id_exemplaire']
        date_debut = date.today()
        date_fin = date_debut + timedelta(days=15)
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO emprunts (id_utilisateur, id_exemplaire, date_debut, date_fin) 
            VALUES (%s, %s, %s, %s)
        """, (id_utilisateur, id_exemplaire, date_debut, date_fin))
        
        # Mettre à jour le statut de l'exemplaire
        cur.execute("""
            UPDATE exemplaires 
            SET statut = 'en prêt' 
            WHERE id_exemplaire = %s
        """, (id_exemplaire,))
        
        mysql.connection.commit()
        cur.close()
        flash('Emprunt ajouté avec succès')
        return redirect(url_for('list_emprunts'))
    
    # Récupérer les utilisateurs et exemplaires disponibles
    cur = mysql.connection.cursor()
    cur.execute("SELECT id_utilisateur, nom FROM utilisateurs")
    utilisateurs = cur.fetchall()
    cur.execute("SELECT id_exemplaire, titre FROM exemplaires e JOIN documents d ON e.reference_document = d.reference WHERE e.statut = 'en rayon'")
    exemplaires = cur.fetchall()
    cur.close()
    
    return render_template('ajouter_emprunt.html', utilisateurs=utilisateurs, exemplaires=exemplaires)

@app.route('/emprunts/retourner/<int:id_emprunt>')
def retourner_emprunt(id_emprunt):
    cur = mysql.connection.cursor()
    # Récupérer l'ID de l'exemplaire
    cur.execute("SELECT id_exemplaire FROM emprunts WHERE id_emprunt = %s", (id_emprunt,))
    id_exemplaire = cur.fetchone()[0]
    
    # Mettre à jour le statut de l'emprunt
    cur.execute("""
        UPDATE emprunts 
        SET statut = 'rendu' 
        WHERE id_emprunt = %s
    """, (id_emprunt,))
    
    # Réactiver l'exemplaire
    cur.execute("""
        UPDATE exemplaires 
        SET statut = 'en rayon' 
        WHERE id_exemplaire = %s
    """, (id_exemplaire,))
    
    mysql.connection.commit()
    cur.close()
    flash('Retour de l\'emprunt effectué')
    return redirect(url_for('list_emprunts'))

# Vérification des retards
@app.route('/emprunts/retards')
def emprunts_retards():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT e.id_emprunt, u.nom, d.titre, e.date_debut, e.date_fin
        FROM emprunts e
        JOIN utilisateurs u ON e.id_utilisateur = u.id_utilisateur
        JOIN exemplaires ex ON e.id_exemplaire = ex.id_exemplaire
        JOIN documents d ON ex.reference_document = d.reference
        WHERE e.statut = 'en cours' AND e.date_fin < CURRENT_DATE
    """)
    retards = cur.fetchall()
    cur.close()
    return render_template('emprunts_retards.html', retards=retards)

if __name__ == "__main__":
    app.run(debug=True)