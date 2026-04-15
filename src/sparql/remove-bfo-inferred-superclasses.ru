PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

DELETE {
  ?child rdfs:subClassOf ?parent .
  ?axiom ?axiom_p ?axiom_o .
}

WHERE {
  ?child rdfs:subClassOf ?parent .
  FILTER(isIRI(?child))
  FILTER(isIRI(?parent))
  FILTER(STRSTARTS(STR(?child), "https://purl.brain-bican.org/ontology/HOMBA"))
  FILTER(STRSTARTS(STR(?parent), "http://purl.obolibrary.org/obo/BFO_"))

  OPTIONAL {
    ?axiom owl:annotatedSource ?child ;
           owl:annotatedProperty rdfs:subClassOf ;
           owl:annotatedTarget ?parent ;
           ?axiom_p ?axiom_o .
  }
}
